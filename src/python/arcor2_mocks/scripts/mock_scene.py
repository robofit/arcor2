#!/usr/bin/env python3

import argparse
import random
import time
from typing import Dict

import humps
from flask import jsonify, request

from arcor2 import env
from arcor2.data import common, object_type, scene
from arcor2.flask import RespT, create_app, run_app
from arcor2_mocks import SCENE_PORT, SCENE_SERVICE_NAME, version

app = create_app(__name__)

collision_objects: Dict[str, object_type.Models] = {}
started: bool = False

delay_mean = env.get_float("ARCOR2_MOCK_SCENE_DELAY_MEAN", 0)
delay_sigma = env.get_float("ARCOR2_MOCK_SCENE_DELAY_SIGMA", 0)


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
    """

    # TODO workarounded because of bug in pyhumps
    # args = humps.decamelize(request.args.to_dict())
    # box = object_type.Box(args["box_id"], float(args["size_x"]), float(args["size_y"]), float(args["size_z"]))

    args = request.args.to_dict()
    box = object_type.Box(args["boxId"], float(args["sizeX"]), float(args["sizeY"]), float(args["sizeZ"]))

    collision_objects[box.id] = box
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
    """

    args = humps.decamelize(request.args.to_dict())
    sphere = object_type.Sphere(args["sphere_id"], float(args["radius"]))
    collision_objects[sphere.id] = sphere
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
    """

    args = humps.decamelize(request.args.to_dict())
    cylinder = object_type.Cylinder(args["cylinder_id"], float(args["radius"]), float(args["height"]))
    collision_objects[cylinder.id] = cylinder
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
              schema:
                type: string
            - name: uri
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
    """

    args = humps.decamelize(request.args.to_dict())
    mesh = object_type.Mesh(args["mesh_id"], args["uri"])
    collision_objects[mesh.id] = mesh
    return jsonify("ok"), 200


@app.route("/collisions/<string:collisionId>", methods=["DELETE"])
def delete_collision(collisionId: str) -> RespT:
    """Deletes collision object.
    ---
    delete:
        tags:
            - Collisions
        summary: Deletes collision object.
        parameters:
            - name: collisionId
              in: path
              description: unique ID
              required: true
              schema:
                type: string
        responses:
            200:
              description: Ok
    """

    try:
        del collision_objects[collisionId]
    except KeyError:
        return jsonify("Not found"), 404

    return jsonify("ok"), 200


@app.route("/collisions", methods=["GET"])
def get_collisions() -> RespT:
    """Gets collision ids.
    ---
    get:
        tags:
        - Collisions
        summary: Gets collision ids.
        responses:
            '200':
              description: Success
              content:
                application/json:
                  schema:
                    type: array
                    items:
                        type: string
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
    """

    return jsonify(common.Pose().to_json())


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
              content:
                  application/json:
                      schema:
                        type: string
    """

    global started
    delay()
    started = True
    return jsonify("ok"), 200


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
              content:
                  application/json:
                      schema:
                        type: string
    """

    global started
    delay()
    started = False
    return jsonify("ok"), 200


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
    """

    return jsonify(started)


def main() -> None:

    parser = argparse.ArgumentParser(description=SCENE_SERVICE_NAME)
    parser.add_argument("-s", "--swagger", action="store_true", default=False)
    args = parser.parse_args()

    run_app(
        app,
        SCENE_SERVICE_NAME,
        version(),
        "0.3.0",
        SCENE_PORT,
        [
            common.Pose,
            object_type.Box,
            object_type.Cylinder,
            object_type.Sphere,
            object_type.Mesh,
            scene.MeshFocusAction,
        ],
        args.swagger,
    )


if __name__ == "__main__":
    main()
