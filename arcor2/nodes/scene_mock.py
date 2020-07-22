#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import json
import os
import uuid
from typing import Dict, Tuple, Union, cast

from apispec import APISpec  # type: ignore

from apispec_webframeworks.flask import FlaskPlugin  # type: ignore

from dataclasses_jsonschema.apispec import DataclassesPlugin

from flask import Flask, Response, jsonify, request

from flask_cors import CORS  # type: ignore

from flask_swagger_ui import get_swaggerui_blueprint  # type: ignore

import arcor2
from arcor2.data import common, object_type
from arcor2.helpers import camel_case_to_snake_case
from arcor2.rest import convert_keys

PORT = int(os.getenv("ARCOR2_SCENE_SERVICE_MOCK_PORT", 5013))
SERVICE_NAME = "ARCOR2 Scene Service Mock"


# Create an APISpec
spec = APISpec(
    title=SERVICE_NAME,
    version=arcor2.version(),
    openapi_version="3.0.2",
    plugins=[FlaskPlugin(), DataclassesPlugin()],
)

app = Flask(__name__)
CORS(app)


def get_id() -> int:
    return uuid.uuid4().int


RespT = Union[Response, Tuple[str, int]]

collision_objects: Dict[str, object_type.Models] = {}


@app.route("/collisions/box", methods=['PUT'])
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

    args = convert_keys(request.args.to_dict(), camel_case_to_snake_case)
    box = object_type.Box(args["box_id"], float(args["size_x"]), float(args["size_y"]), float(args["size_z"]))
    collision_objects[box.id] = box
    return "ok", 200


@app.route("/collisions/sphere", methods=['PUT'])
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

    args = convert_keys(request.args.to_dict(), camel_case_to_snake_case)
    sphere = object_type.Sphere(args["sphere_id"], float(args["radius"]))
    collision_objects[sphere.id] = sphere
    return "ok", 200


@app.route("/collisions/cylinder", methods=['PUT'])
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

    args = convert_keys(request.args.to_dict(), camel_case_to_snake_case)
    cylinder = object_type.Cylinder(args["cylinder_id"], float(args["radius"]), float(args["height"]))
    collision_objects[cylinder.id] = cylinder
    return "ok", 200


@app.route("/collisions/mesh", methods=['PUT'])
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
                    default: 1
                - name: meshScaleY
                  in: query
                  schema:
                    type: number
                    format: float
                    default: 1
                - name: meshScaleZ
                  in: query
                  schema:
                    type: number
                    format: float
                    default: 1
            requestBody:
                  content:
                    application/json:
                      schema:
                        $ref: Pose
            responses:
                200:
                  description: Ok
    """

    args = convert_keys(request.args.to_dict(), camel_case_to_snake_case)
    mesh = object_type.Mesh(args["mesh_id"], args["uri"])
    collision_objects[mesh.id] = mesh
    return "ok", 200


@app.route("/collisions/<string:collisionId>", methods=['DELETE'])
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
        return "Not found", 404

    return "ok", 200


@app.route("/collisions", methods=['GET'])
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

    return cast(Response, jsonify(list(collision_objects.keys())))


@app.route("/utils/focus", methods=['PUT'])
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

    return cast(Response, jsonify(common.Pose().to_json()))


@app.route("/swagger/api/swagger.json", methods=["GET"])
def get_swagger() -> str:
    return json.dumps(spec.to_dict())


spec.components.schema(common.Pose.__name__, schema=common.Pose)
spec.components.schema(object_type.Box.__name__, schema=object_type.Box)
spec.components.schema(object_type.Cylinder.__name__, schema=object_type.Cylinder)
spec.components.schema(object_type.Sphere.__name__, schema=object_type.Sphere)
spec.components.schema(object_type.Mesh.__name__, schema=object_type.Mesh)
spec.components.schema(object_type.MeshFocusAction.__name__, schema=object_type.MeshFocusAction)


with app.test_request_context():

    spec.path(view=put_sphere)
    spec.path(view=put_box)
    spec.path(view=put_focus)
    spec.path(view=put_mesh)
    spec.path(view=put_cylinder)
    spec.path(view=delete_collision)
    spec.path(view=get_collisions)


def main() -> None:

    parser = argparse.ArgumentParser(description=SERVICE_NAME)
    parser.add_argument('-s', '--swagger', action="store_true", default=False)
    args = parser.parse_args()

    if args.swagger:
        print(spec.to_yaml())
        return

    SWAGGER_URL = "/swagger"

    swaggerui_blueprint = get_swaggerui_blueprint(
        SWAGGER_URL,  # Swagger UI static files will be mapped to '{SWAGGER_URL}/dist/'
        "./api/swagger.json"
    )

    # Register blueprint at URL
    app.register_blueprint(swaggerui_blueprint, url_prefix=SWAGGER_URL)

    app.run(host='0.0.0.0', port=PORT)


if __name__ == '__main__':
    main()
