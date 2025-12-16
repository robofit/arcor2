#!/usr/bin/env python3

import argparse
import logging
import os
from dataclasses import dataclass, field
from functools import wraps

import humps
from ament_index_python.packages import get_package_share_directory  # pants: no-infer-dep
from flask import Response, jsonify, request
from moveit_configs_utils import MoveItConfigsBuilder  # pants: no-infer-dep

from arcor2 import env
from arcor2.data import common, object_type
from arcor2.data.common import Joint, Pose
from arcor2.data.robot import InverseKinematicsRequest
from arcor2.helpers import port_from_url
from arcor2.logging import get_logger
from arcor2_ur import get_data, version
from arcor2_ur.exceptions import NotFound, StartError, UrGeneral, WebApiError
from arcor2_ur.object_types.ur5e import Vacuum
from arcor2_ur.scripts.ros_worker import CollisionObjectTuple, RosWorkerClient
from arcor2_web.flask import RespT, create_app, run_app

logger = get_logger(__name__)

URL = os.getenv("ARCOR2_UR_URL", "http://localhost:5012")
BASE_LINK = os.getenv("ARCOR2_UR_BASE_LINK", "base_link")
TOOL_LINK = os.getenv("ARCOR2_UR_TOOL_LINK", "tool0")
UR_TYPE = os.getenv("ARCOR2_UR_TYPE", "ur5e")
PLANNING_GROUP_NAME = os.getenv("ARCOR2_UR_PLANNING_GROUP_NAME", "ur_manipulator")
ROBOT_IP = os.getenv("ARCOR2_UR_ROBOT_IP", "")
VGC10_PORT = env.get_int("ARCOR2_UR_VGC10_PORT", 54321)
INTERACT_WITH_DASHBOARD = env.get_bool("ARCOR2_UR_INTERACT_WITH_DASHBOARD", True)

SERVICE_NAME = f"UR Web API ({UR_TYPE})"


@dataclass
class ServiceState:
    pose: Pose
    worker: RosWorkerClient


@dataclass
class Globs:
    debug = False
    state: ServiceState | None = None
    collision_objects: dict[str, CollisionObjectTuple] = field(default_factory=dict)
    scene_started = False  # flag for "Scene service"


globs: Globs = Globs()
app = create_app(__name__)

# this is normally specified in a launch file
moveit_config = (
    MoveItConfigsBuilder(robot_name="ur", package_name="ur_moveit_config")
    .robot_description(
        os.path.join(get_package_share_directory("ur_description"), "urdf", "ur.urdf.xacro"),
        {"name": "ur", "ur_type": UR_TYPE},
    )
    .robot_description_semantic(
        os.path.join(get_package_share_directory("ur_moveit_config"), "srdf", "ur.srdf.xacro"), {"name": UR_TYPE}
    )
    .trajectory_execution(
        os.path.join(get_package_share_directory("ur_moveit_config"), "config", "moveit_controllers.yaml")
    )
    .robot_description_kinematics(
        os.path.join(get_package_share_directory("ur_moveit_config"), "config", "kinematics.yaml")
    )
    .moveit_cpp(file_path=get_data("moveit.yaml"))
    .to_moveit_configs()
).to_dict()


def started() -> bool:
    return globs.state is not None


def requires_started(f):
    @wraps(f)
    def wrapped(*args, **kwargs):
        if not started():
            raise StartError("Not started")
        return f(*args, **kwargs)

    return wrapped


@app.route("/system/start", methods=["PUT"])  # for compatibility with Scene service
def put_start_scene() -> RespT:
    """Start the scene (compatibility)."""
    globs.scene_started = True
    return Response(status=200)


@app.route("/state/start", methods=["PUT"])
def put_start() -> RespT:
    """Start the robot.
    ---
    put:
        description: Start the robot.
        tags:
           - State
        requestBody:
              content:
                application/json:
                  schema:
                    $ref: Pose
        responses:
            204:
              description: Ok
            500:
              description: "Error types: **General**, **UrGeneral**, **StartError**."
              content:
                application/json:
                  schema:
                    $ref: WebApiError
    """
    if started():
        raise UrGeneral("Already started.")

    if not isinstance(request.json, dict):
        raise UrGeneral("Body should be a JSON dict containing Pose.")

    pose = Pose.from_dict(request.json)
    worker = RosWorkerClient(
        pose,
        globs.collision_objects,
        BASE_LINK,
        TOOL_LINK,
        PLANNING_GROUP_NAME,
        moveit_config,
        INTERACT_WITH_DASHBOARD,
        ROBOT_IP,
        VGC10_PORT,
        globs.debug,
    )
    globs.state = ServiceState(pose, worker)

    return Response(status=204)


@app.route("/system/stop", methods=["PUT"])  # for compatibility with Scene service
def put_stop_scene() -> RespT:
    """Stop the scene (compatibility)."""
    globs.scene_started = False
    return Response(status=204)


@app.route("/state/stop", methods=["PUT"])
@requires_started
def put_stop() -> RespT:
    """Stop the robot.
    ---
    put:
        description: Stop the robot.
        tags:
           - State
        responses:
            204:
              description: Ok
            500:
              description: "Error types: **General**, **StartError**."
              content:
                application/json:
                  schema:
                    $ref: WebApiError
    """
    if not started():
        raise UrGeneral("Not started!")

    assert globs.state

    globs.state.worker.stop()
    globs.state = None

    return Response(status=204)


@app.route("/system/running", methods=["GET"])  # for compatibility with Scene service
def get_stated_scene() -> RespT:
    """Return whether scene is running (compatibility)."""
    return jsonify(globs.scene_started)


@app.route("/state/started", methods=["GET"])
def get_started() -> RespT:
    """Get service started flag."""
    return jsonify(started())


@app.route("/collisions/box", methods=["PUT"])
def put_box() -> RespT:
    """Add or update collision box.
    ---
    put:
        tags:
            - Collisions
        description: Add or update collision box.
        parameters:
            - name: boxId
              in: query
              description: unique box collision ID
              required: true
              schema:
                type: string
            - name: sizeX
              in: query
              schema:
                type: number
                format: float
            - name: sizeY
              in: query
              schema:
                type: number
                format: float
            - name: sizeZ
              in: query
              schema:
                type: number
                format: float
        requestBody:
              content:
                application/json:
                  schema:
                    $ref: Pose
        responses:
            204:
                description: Ok
            500:
                description: "Error types: **General**, **SceneGeneral**."
                content:
                    application/json:
                        schema:
                            $ref: WebApiError
    """
    if not isinstance(request.json, dict):
        raise UrGeneral("Body should be a JSON dict containing Pose.")

    args = request.args.to_dict()
    box = object_type.Box(args["boxId"], float(args["sizeX"]), float(args["sizeY"]), float(args["sizeZ"]))
    globs.collision_objects[box.id] = CollisionObjectTuple(box, common.Pose.from_dict(humps.decamelize(request.json)))

    if started():
        assert globs.state
        globs.state.worker.request("update_collisions", collision_objects=globs.collision_objects)

    return Response(status=204)


@app.route("/collisions/sphere", methods=["PUT"])
def put_sphere() -> RespT:
    """Add or update collision sphere.
    ---
    put:
        tags:
            - Collisions
        description: Add or update collision sphere.
        parameters:
            - name: sphereId
              in: query
              description: unique sphere collision ID
              required: true
              schema:
                type: string
            - name: radius
              in: query
              schema:
                type: number
                format: float
        requestBody:
              content:
                application/json:
                  schema:
                    $ref: Pose
        responses:
            204:
              description: Ok
            500:
              description: "Error types: **General**, **SceneGeneral**."
              content:
                application/json:
                  schema:
                    $ref: WebApiError
    """
    if not isinstance(request.json, dict):
        raise UrGeneral("Body should be a JSON dict containing Pose.")

    args = humps.decamelize(request.args.to_dict())
    sphere = object_type.Sphere(args["sphere_id"], float(args["radius"]))
    globs.collision_objects[sphere.id] = CollisionObjectTuple(
        sphere, common.Pose.from_dict(humps.decamelize(request.json))
    )

    logger.warning("Sphere collision object added but will be ignored as only boxes are supported at the moment.")

    if started():
        assert globs.state
        globs.state.worker.request("update_collisions", collision_objects=globs.collision_objects)

    return Response(status=204)


@app.route("/collisions/cylinder", methods=["PUT"])
def put_cylinder() -> RespT:
    """Add or update collision cylinder.
    ---
    put:
        tags:
            - Collisions
        description: Add or update collision cylinder.
        parameters:
            - name: cylinderId
              in: query
              description: unique cylinder collision ID
              required: true
              schema:
                type: string
            - name: radius
              in: query
              schema:
                type: number
                format: float
            - name: height
              in: query
              schema:
                type: number
                format: float
        requestBody:
              content:
                application/json:
                  schema:
                    $ref: Pose
        responses:
            200:
              description: Ok
              content:
                application/json:
                  schema:
                    type: string
            500:
              description: "Error types: **General**, **SceneGeneral**."
              content:
                application/json:
                  schema:
                    $ref: WebApiError
    """
    if not isinstance(request.json, dict):
        raise UrGeneral("Body should be a JSON dict containing Pose.")

    args = humps.decamelize(request.args.to_dict())
    cylinder = object_type.Cylinder(args["cylinder_id"], float(args["radius"]), float(args["height"]))
    globs.collision_objects[cylinder.id] = CollisionObjectTuple(
        cylinder, common.Pose.from_dict(humps.decamelize(request.json))
    )

    logger.warning("Cylinder collision object added but will be ignored as only boxes are supported at the moment.")

    if started():
        assert globs.state
        globs.state.worker.request("update_collisions", collision_objects=globs.collision_objects)

    return Response(status=204)


@app.route("/collisions/mesh", methods=["PUT"])
def put_mesh() -> RespT:
    """Add or update collision mesh.
    ---
    put:
        tags:
            - Collisions
        description: Add or update collision mesh.
        parameters:
            - name: meshId
              in: query
              description: unique mesh collision ID
              required: true
              schema:
                type: string
            - name: meshFileId
              in: query
              schema:
                type: string
            - name: meshScaleX
              in: query
              schema:
                type: number
                format: float
                default: 1.0
            - name: meshScaleY
              in: query
              schema:
                type: number
                format: float
                default: 1.0
            - name: meshScaleZ
              in: query
              schema:
                type: number
                format: float
                default: 1.0
        requestBody:
              content:
                application/json:
                  schema:
                    $ref: Pose
        responses:
            204:
              description: Ok
            500:
              description: "Error types: **General**, **SceneGeneral**."
              content:
                application/json:
                  schema:
                    $ref: WebApiError
    """
    if not isinstance(request.json, dict):
        raise UrGeneral("Body should be a JSON dict containing Pose.")

    args = humps.decamelize(request.args.to_dict())
    mesh = object_type.Mesh(args["mesh_id"], args["mesh_file_id"])
    globs.collision_objects[mesh.id] = CollisionObjectTuple(mesh, common.Pose.from_dict(humps.decamelize(request.json)))

    logger.warning("Mesh collision object added but will be ignored as only boxes are supported at the moment.")

    if started():
        assert globs.state
        globs.state.worker.request("update_collisions", collision_objects=globs.collision_objects)

    return Response(status=204)


@app.route("/collisions/<string:id>", methods=["DELETE"])
def delete_collision(id: str) -> RespT:
    """Deletes collision object.
    ---
    delete:
        tags:
            - Collisions
        summary: Deletes collision object.
        parameters:
            - name: id
              in: path
              description: unique ID
              required: true
              schema:
                type: string
        responses:
            204:
              description: Ok
            500:
              description: "Error types: **General**, **NotFound**."
              content:
                application/json:
                  schema:
                    $ref: WebApiError
    """
    try:
        del globs.collision_objects[id]
    except KeyError:
        raise NotFound("Collision not found")

    if started():
        assert globs.state
        globs.state.worker.request("update_collisions", collision_objects=globs.collision_objects)

    return Response(status=200)


@app.route("/collisions", methods=["GET"])
def get_collisions() -> RespT:
    """Gets collision ids.
    ---
    get:
        tags:
        - Collisions
        summary: Gets collision ids.
        responses:
            200:
              description: Success
              content:
                application/json:
                  schema:
                    type: array
                    items:
                      type: string
            500:
              description: "Error types: **General**."
              content:
                application/json:
                  schema:
                    $ref: WebApiError
    """
    return jsonify(list(globs.collision_objects.keys()))


@app.route("/joints", methods=["GET"])
@requires_started
def get_joints() -> RespT:
    """Get the current state.
    ---
    get:
        description: Get the current state.
        tags:
           - Robot
        responses:
            200:
              description: Ok
              content:
                application/json:
                    schema:
                        type: array
                        items:
                            $ref: Joint
            500:
              description: "Error types: **General**, **StartError**."
              content:
                application/json:
                  schema:
                    $ref: WebApiError
    """
    assert globs.state
    return jsonify(globs.state.worker.request("get_joints"))


@app.route("/ik", methods=["PUT"])
@requires_started
def put_ik() -> RespT:
    """Get the current state.
    ---
    put:
        description: Get the current state.
        tags:
           - Robot
        requestBody:
              content:
                application/json:
                  schema:
                    $ref: InverseKinematicsRequest
        responses:
            200:
              description: Ok
              content:
                application/json:
                    schema:
                        type: array
                        items:
                            $ref: Joint
            500:
              description: "Error types: **General**, **DobotGeneral**, **StartError**."
              content:
                application/json:
                  schema:
                    $ref: WebApiError
    """
    assert globs.state

    if not isinstance(request.json, dict):
        raise UrGeneral("Body should be a JSON dict containing InverseKinematicsRequest.")

    ikr = InverseKinematicsRequest.from_dict(request.json)
    logger.debug(f"Got IK request: {ikr}")
    result = globs.state.worker.request("ik", ikr=ikr.to_dict())
    return jsonify(result)


@app.route("/hand_teaching", methods=["GET"])
@requires_started
def get_hand_teaching() -> RespT:
    """Get hand teaching status.
    ---
    get:
        description: Get hand teaching status.
        tags:
           - Robot
        responses:
            200:
              description: Ok
              content:
                application/json:
                    schema:
                        type: boolean
            500:
              description: "Error types: **General**, **StartError**."
              content:
                application/json:
                  schema:
                    $ref: WebApiError
    """
    assert globs.state
    return jsonify(globs.state.worker.request("get_freedrive_mode"))


@app.route("/hand_teaching", methods=["PUT"])
@requires_started
def put_hand_teaching() -> RespT:
    """Set hand teaching status.
    ---
    put:
        description: Set hand teaching status.
        tags:
           - Robot
        parameters:
            - in: query
              name: enabled
              schema:
                type: boolean
        responses:
            204:
              description: Ok
            500:
              description: "Error types: **General**, **StartError**."
              content:
                application/json:
                  schema:
                    $ref: WebApiError
    """
    assert globs.state

    enabled = request.args.get("enabled", default="false").lower() == "true"
    globs.state.worker.request("set_freedrive_mode", enabled=enabled)

    return Response(status=204)


@app.route("/eef/pose", methods=["GET"])
@requires_started
def get_eef_pose() -> RespT:
    """Get the EEF pose.
    ---
    get:
        description: Get the EEF pose.
        tags:
           - Robot
        responses:
            200:
              description: Ok
              content:
                application/json:
                    schema:
                        $ref: Pose
            500:
              description: "Error types: **General**, **StartError**."
              content:
                application/json:
                  schema:
                    $ref: WebApiError
    """
    assert globs.state
    pose = globs.state.worker.request("get_eef_pose")
    return jsonify(pose), 200


@app.route("/eef/pose", methods=["PUT"])
@requires_started
def put_eef_pose() -> RespT:
    """Set the EEF pose.
    ---
    put:
        description: Set the EEF pose.
        tags:
           - Robot
        parameters:
            - name: velocity
              in: query
              schema:
                type: number
                format: float
                minimum: 0
                maximum: 100
                default: 50
            - name: payload
              in: query
              schema:
                type: number
                format: float
                minimum: 0
                maximum: 5
                default: 0
            - in: query
              name: safe
              schema:
                type: boolean
                default: true
        requestBody:
              content:
                application/json:
                  schema:
                    $ref: Pose
        responses:
            200:
              description: Ok
            500:
              description: "Error types: **General**, **UrGeneral**, **StartError**, **NotFound**."
              content:
                application/json:
                  schema:
                    $ref: WebApiError
    """
    assert globs.state

    if not isinstance(request.json, dict):
        raise UrGeneral("Body should be a JSON dict containing Pose.")

    pose = Pose.from_dict(request.json)
    velocity = float(request.args.get("velocity", default=50.0)) / 100.0
    payload = float(request.args.get("payload", default=0.0))
    safe = request.args.get("safe", default="true") == "true"

    globs.state.worker.request("move_to_pose", pose=pose.to_dict(), velocity=velocity, payload=payload, safe=safe)
    return Response(status=204)


@app.route("/suction/suck", methods=["PUT"])
@requires_started
def put_suck() -> RespT:
    """Turn on suction.
    ---
    put:
        description: Get the current state.
        tags:
           - Tool
        parameters:
            - name: vacuum
              in: query
              schema:
                type: integer
                minimum: 0
                maximum: 80
                default: 60
              description: Tells how hard to grasp in the range of 0% to 80 % vacuum.
        responses:
            204:
              description: Ok
            500:
              description: "Error types: **General**, **StartError**."
              content:
                application/json:
                  schema:
                    $ref: WebApiError
    """
    assert globs.state

    vacuum = int(request.args.get("vacuum", default=60))
    globs.state.worker.request("suck", vacuum=vacuum)

    return Response(status=204)


@app.route("/suction/vacuum", methods=["GET"])
@requires_started
def get_vacuum() -> RespT:
    """Gets vacuum value.
    ---
    get:
        description: Get the measured vacuum.
        tags:
           - Tool
        responses:
            200:
              description: Returns current relative vacuum on each channel.
              content:
                application/json:
                  schema:
                    $ref: Vacuum
            500:
              description: "Error types: **General**, **StartError**."
              content:
                application/json:
                  schema:
                    $ref: WebApiError
    """
    assert globs.state
    return jsonify(globs.state.worker.request("vacuum"))


@app.route("/suction/release", methods=["PUT"])
@requires_started
def put_release() -> RespT:
    """Turn off suction.
    ---
    put:
        description: Get the current state.
        tags:
           - Tool
        responses:
            204:
              description: Ok
            500:
              description: "Error types: **General**, **StartError**."
              content:
                application/json:
                  schema:
                    $ref: WebApiError
    """
    assert globs.state
    globs.state.worker.request("release")
    return Response(status=204)


def main() -> None:
    parser = argparse.ArgumentParser(description=SERVICE_NAME)
    parser.add_argument("-s", "--swagger", action="store_true", default=False)

    parser.add_argument(
        "-d",
        "--debug",
        help="Set logging level to debug.",
        action="store_const",
        const=logging.DEBUG,
        default=logging.DEBUG if env.get_bool("ARCOR2_UR_DEBUG") else logging.INFO,
    )

    args = parser.parse_args()
    logger.setLevel(args.debug)
    globs.debug = args.debug

    if not INTERACT_WITH_DASHBOARD:
        logger.warning("Interaction with robot dashboard disabled. Make sure you know what it means.")

    run_app(
        app,
        SERVICE_NAME,
        version(),
        port_from_url(URL),
        [Vacuum, Pose, Joint, InverseKinematicsRequest, WebApiError],
        args.swagger,
    )

    if globs.state:
        globs.state.worker.stop()


if __name__ == "__main__":
    main()
