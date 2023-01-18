#!/usr/bin/env python3

import argparse
import logging
import math
import random
import time
from typing import NamedTuple

import humps
import numpy as np
import open3d as o3d
import quaternion
from flask import jsonify, request

from arcor2 import env
from arcor2.data import common, object_type, scene
from arcor2.flask import Response, RespT, create_app, run_app
from arcor2.logging import get_logger
from arcor2_scene import SCENE_PORT, SCENE_SERVICE_NAME, version
from arcor2_scene.exceptions import NotFound, SceneGeneral, WebApiError

app = create_app(__name__)
logger = get_logger(__name__)
logger.propagate = False


class CollisionObject(NamedTuple):

    model: object_type.Models
    pose: common.Pose


collision_objects: dict[str, CollisionObject] = {}
started: bool = False
inflation = 0.01

delay_mean = env.get_float("ARCOR2_SCENE_DELAY_MEAN", 0)
delay_sigma = env.get_float("ARCOR2_SCENE_DELAY_SIGMA", 0)


def delay() -> None:
    """This is to simulate the long-starting Scene service.

    Could be useful to uncover specific kind of bugs.
    :return:
    """
    time.sleep(random.normalvariate(delay_mean, delay_sigma))


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
        raise SceneGeneral("Body should be a JSON dict containing Pose.")

    args = request.args.to_dict()
    box = object_type.Box(args["boxId"], float(args["sizeX"]), float(args["sizeY"]), float(args["sizeZ"]))
    collision_objects[box.id] = CollisionObject(box, common.Pose.from_dict(humps.decamelize(request.json)))

    return jsonify("ok"), 200


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
        raise SceneGeneral("Body should be a JSON dict containing Pose.")

    args = humps.decamelize(request.args.to_dict())
    sphere = object_type.Sphere(args["sphere_id"], float(args["radius"]))
    collision_objects[sphere.id] = CollisionObject(sphere, common.Pose.from_dict(humps.decamelize(request.json)))
    return jsonify("ok"), 200


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
        raise SceneGeneral("Body should be a JSON dict containing Pose.")

    args = humps.decamelize(request.args.to_dict())
    cylinder = object_type.Cylinder(args["cylinder_id"], float(args["radius"]), float(args["height"]))
    collision_objects[cylinder.id] = CollisionObject(cylinder, common.Pose.from_dict(humps.decamelize(request.json)))
    return jsonify("ok"), 200


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
        raise SceneGeneral("Body should be a JSON dict containing Pose.")

    args = humps.decamelize(request.args.to_dict())
    mesh = object_type.Mesh(args["mesh_id"], args["mesh_file_id"])
    collision_objects[mesh.id] = CollisionObject(mesh, common.Pose.from_dict(humps.decamelize(request.json)))
    return jsonify("ok"), 200


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
            200:
              description: Ok
            500:
              description: "Error types: **General**, **NotFound**."
              content:
                application/json:
                  schema:
                    $ref: WebApiError
    """

    try:
        del collision_objects[id]
    except KeyError:
        raise NotFound("Collision not found")

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

    return jsonify(list(collision_objects.keys()))


@app.route("/utils/focus", methods=["PUT"])
def put_focus() -> RespT:
    """Calculates position of object.
    ---
    put:
        tags:
            - Utils
        description: Calculates position of object.
        requestBody:
              content:
                application/json:
                  schema:
                    $ref: MeshFocusAction
        responses:
            200:
              description: Ok
              content:
                application/json:
                  schema:
                    $ref: Pose
            500:
              description: "Error types: **General**."
              content:
                application/json:
                  schema:
                    $ref: WebApiError
    """

    return jsonify(common.Pose().to_dict())


@app.route("/utils/line-safe", methods=["PUT"])
def put_line_safe() -> RespT:
    """Checks whether the line between two points intersects any object.
    ---
    put:
        tags:
            - Utils
        description: Returns true if line is safe (without collisions).
        requestBody:
              content:
                application/json:
                  schema:
                    $ref: LineCheck
        responses:
            200:
              description: Ok
              content:
                application/json:
                  schema:
                    $ref: LineCheckResult
            500:
              description: "Error types: **General**, **SceneGeneral**."
              content:
                application/json:
                  schema:
                    $ref: WebApiError
    """

    if not isinstance(request.json, dict):
        raise SceneGeneral("Body should be a JSON dict containing LineCheck.")

    if not collision_objects:
        logger.debug("Safe. No collision object.")
        return jsonify(scene.LineCheckResult(True).to_dict())

    pts = scene.LineCheck.from_dict(request.json)

    logger.debug(f"pt1: {pts.pt1}")
    logger.debug(f"pt2: {pts.pt2}")

    o3d_scene = o3d.t.geometry.RaycastingScene()
    o3d_id: dict[str, str] = {}  # o3d id to our id

    """
    o3d uses different coordinates, but in this case it should not matter

    o3d        x right,   y down, z forward
    arcor2/ros x forward, y left, z up
    unity      x Right,   y Up,   z Forward
    """
    for obj_id, (model, pose) in collision_objects.items():

        if isinstance(model, object_type.Box):

            # The left bottom corner on the front will be placed at (0, 0, 0)
            sx = model.size_x + inflation
            sy = model.size_y + inflation
            sz = model.size_z + inflation

            tm = o3d.geometry.TriangleMesh.create_box(sx, sy, sz)

            tm = tm.translate([pose.position.x - sx / 2, pose.position.y - sy / 2, pose.position.z - sz / 2])
        elif isinstance(model, object_type.Cylinder):
            tm = o3d.geometry.TriangleMesh.create_cylinder(model.radius + inflation, model.height + inflation)
        elif isinstance(model, object_type.Sphere):
            tm = o3d.geometry.TriangleMesh.create_sphere(model.radius + inflation)
        else:  # TODO mesh
            logger.warning(f"Unsupported type of collision model: {model.type()}.")
            continue

        tm.rotate(quaternion.as_rotation_matrix(pose.orientation.as_quaternion()))
        tm = o3d.t.geometry.TriangleMesh.from_legacy(tm)
        o3d_id[o3d_scene.add_triangles(tm)] = obj_id

    dir_vec = np.array([pts.pt2.x - pts.pt1.x, pts.pt2.y - pts.pt1.y, pts.pt2.z - pts.pt1.z])
    dir_vec = dir_vec / np.linalg.norm(dir_vec)

    logger.debug(f"Direction: {dir_vec}")

    rays = o3d.core.Tensor(
        [[pts.pt1.x, pts.pt1.y, pts.pt1.z, dir_vec[0], dir_vec[1], dir_vec[2]]],
        dtype=o3d.core.Dtype.Float32,
    )
    ans = o3d_scene.cast_rays(rays)
    dist_btw_points = math.dist(pts.pt1, pts.pt2)

    dist_to_hit = float(ans["t_hit"].numpy()[0])

    if dist_to_hit > dist_btw_points:
        logger.debug(
            f"Safe. Distance to hit {dist_to_hit:.3f} larger than distance between points {dist_btw_points:.3f}."
        )
        return jsonify(scene.LineCheckResult(True).to_dict())

    collision_with = o3d_id[ans["geometry_ids"].numpy()[0]]

    logger.debug(f"Unsafe. Distance to hit {dist_to_hit:.3f}, there is collision with {collision_with}.")
    return jsonify(scene.LineCheckResult(False, collision_with))


@app.route("/system/start", methods=["PUT"])
def put_start() -> RespT:
    """Starts the system.
    ---
    put:
        tags:
            - System
        description: Starts the system.
        responses:
            200:
              description: Ok
            500:
              description: "Error types: **General**."
              content:
                application/json:
                  schema:
                    $ref: WebApiError
    """

    global started
    delay()
    started = True
    return Response(status=200)


@app.route("/system/stop", methods=["PUT"])
def put_stop() -> RespT:
    """Stops the system.
    ---
    put:
        tags:
            - System
        description: Stops the system.
        responses:
            200:
              description: Ok
            500:
              description: "Error types: **General**."
              content:
                application/json:
                  schema:
                    $ref: WebApiError
    """

    global started
    if started:
        delay()
    started = False
    collision_objects.clear()
    return Response(status=200)


@app.route("/system/running", methods=["GET"])
def get_started() -> RespT:
    """Gets system state.
    ---
    get:
        tags:
            - System
        description: Gets system state.
        responses:
            200:
              description: Ok
              content:
                application/json:
                  schema:
                    type: boolean
            500:
              description: "Error types: **General**."
              content:
                application/json:
                  schema:
                    $ref: WebApiError
    """

    return jsonify(started)


def main() -> None:

    global inflation

    parser = argparse.ArgumentParser(description=SCENE_SERVICE_NAME)
    parser.add_argument("-s", "--swagger", action="store_true", default=False)

    parser.add_argument(
        "-d",
        "--debug",
        help="Set logging level to debug.",
        action="store_const",
        const=logging.DEBUG,
        default=logging.DEBUG if env.get_bool("ARCOR2_SCENE_DEBUG") else logging.INFO,
    )

    parser.add_argument(
        "-i",
        "--inflation",
        help="How much to inflate collision objects (meters).",
        nargs="?",
        default=env.get_float("ARCOR2_SCENE_INFLATION", 0.01),
        type=float,
    )

    args = parser.parse_args()

    logger.setLevel(args.debug)
    inflation = args.inflation

    run_app(
        app,
        SCENE_SERVICE_NAME,
        version(),
        SCENE_PORT,
        [
            WebApiError,
            common.Pose,
            object_type.Box,
            object_type.Cylinder,
            object_type.Sphere,
            object_type.Mesh,
            scene.MeshFocusAction,
            scene.LineCheck,
            scene.LineCheckResult,
        ],
        args.swagger,
        api_version="0.5.0",
    )


if __name__ == "__main__":
    main()
