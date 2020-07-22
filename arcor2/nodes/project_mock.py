#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import json
import os
import uuid
from datetime import datetime, timezone
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

PORT = int(os.getenv("ARCOR2_PROJECT_SERVICE_MOCK_PORT", 5012))
SERVICE_NAME = "ARCOR2 Project Service Mock"


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


SCENES: Dict[str, common.Scene] = {}
PROJECTS: Dict[str, common.Project] = {}
OBJECT_TYPES: Dict[str, object_type.ObjectType] = {}

BOXES: Dict[str, object_type.Box] = {}
CYLINDERS: Dict[str, object_type.Cylinder] = {}
SPHERES: Dict[str, object_type.Sphere] = {}


@app.route("/project", methods=['PUT'])
def put_project() -> RespT:
    """Add or update project.
        ---
        put:
            tags:
                - Project
            description: Add or update project.
            requestBody:
                  content:
                    application/json:
                      schema:
                        $ref: Project
            responses:
                200:
                  description: Ok
    """

    project = common.Project.from_dict(convert_keys(request.json, camel_case_to_snake_case))
    project.modified = datetime.now(tz=timezone.utc)
    PROJECTS[project.id] = project
    return "ok", 200


@app.route("/project/<string:id>", methods=['GET'])
def get_project(id: str) -> RespT:
    """Add or update project.
        ---
        get:
            tags:
                - Project
            summary: Gets projet by project id.
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
                  content:
                    application/json:
                        schema:
                            $ref: Project
    """

    try:
        return cast(Response, jsonify(PROJECTS[id].to_dict()))
    except KeyError:
        return "Not found", 404


@app.route("/project/<string:id>", methods=['DELETE'])
def delete_project(id: str) -> RespT:
    """Deletes project.
        ---
        delete:
            tags:
                - Project
            summary: Deletes project.
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
    """

    try:
        del PROJECTS[id]
    except KeyError:
        return "Not found", 404

    return "ok", 200


@app.route("/projects", methods=['GET'])
def get_projects() -> RespT:
    """Add or update project.
        ---
        get:
            tags:
            - Project
            summary: Gets all projects id and description.
            responses:
                '200':
                  description: Success
                  content:
                    application/json:
                      schema:
                        $ref: IdDescList
    """

    ret = common.IdDescList()

    for proj in PROJECTS.values():
        ret.items.append(common.IdDesc(proj.id, proj.name, proj.desc))

    return cast(Response, jsonify(ret.to_dict()))


@app.route("/scene", methods=['PUT'])
def put_scene() -> RespT:
    """Add or update scene.
        ---
        put:
            tags:
                - Scene
            description: Add or update scene.
            requestBody:
                  content:
                    application/json:
                      schema:
                        $ref: Scene
            responses:
                200:
                  description: Ok
    """

    scene = common.Scene.from_dict(convert_keys(request.json, camel_case_to_snake_case))
    scene.modified = datetime.now(tz=timezone.utc)
    SCENES[scene.id] = scene
    return "ok", 200


@app.route("/scene/<string:id>", methods=['GET'])
def get_scene(id: str) -> RespT:
    """Add or update scene.
        ---
        get:
            tags:
                - Scene
            summary: Gets scene by project id.
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
                  content:
                    application/json:
                        schema:
                            $ref: Scene
    """

    try:
        return cast(Response, jsonify(SCENES[id].to_dict()))
    except KeyError:
        return "Not found", 404


@app.route("/scene/<string:id>", methods=['DELETE'])
def delete_scene(id: str) -> RespT:
    """Deletes scene.
        ---
        delete:
            tags:
                - Scene
            summary: Deletes scene.
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
    """

    try:
        del SCENES[id]
    except KeyError:
        return "Not found", 404

    return "ok", 200


@app.route("/scenes", methods=['GET'])
def get_scenes() -> RespT:
    """Add or update scene.
        ---
        get:
            tags:
            - Scene
            summary: Gets all scenes id and description.
            responses:
                '200':
                  description: Success
                  content:
                    application/json:
                      schema:
                        $ref: IdDescList
    """

    ret = common.IdDescList()

    for scene in SCENES.values():
        ret.items.append(common.IdDesc(scene.id, scene.name, scene.desc))

    return cast(Response, jsonify(ret.to_dict()))


@app.route("/object_type", methods=['PUT'])
def put_object_type() -> RespT:
    """Add or update object type.
        ---
        put:
            tags:
                - ObjectType
            description: Add or update object type.
            requestBody:
                  content:
                    application/json:
                      schema:
                        $ref: ObjectType
            responses:
                200:
                  description: Ok
    """

    obj_type = object_type.ObjectType.from_dict(convert_keys(request.json, camel_case_to_snake_case))
    OBJECT_TYPES[obj_type.id] = obj_type
    return "ok", 200


@app.route("/object_types/<string:id>", methods=['GET'])
def get_object_type(id: str) -> RespT:
    """Add or update object_type.
        ---
        get:
            tags:
                - ObjectType
            summary: Gets object_type by project id.
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
                  content:
                    application/json:
                        schema:
                            $ref: ObjectType
    """

    try:
        return cast(Response, jsonify(OBJECT_TYPES[id].to_dict()))
    except KeyError:
        return "Not found", 404


@app.route("/object_type/<string:id>", methods=['DELETE'])
def delete_object_type(id: str) -> RespT:
    """Deletes object type.
        ---
        delete:
            tags:
                - ObjectType
            summary: Deletes object type.
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
    """

    try:
        del OBJECT_TYPES[id]
    except KeyError:
        return "Not found", 404

    return "ok", 200


@app.route("/object_types", methods=['GET'])
def get_object_types() -> RespT:
    """Add or update ObjectType.
        ---
        get:
            tags:
            - ObjectType
            summary: Gets all object types id and description.
            responses:
                '200':
                  description: Success
                  content:
                    application/json:
                      schema:
                        $ref: IdDescList
    """

    ret = common.IdDescList()

    for obj_type in OBJECT_TYPES.values():
        ret.items.append(common.IdDesc(obj_type.id, "", obj_type.desc))

    return cast(Response, jsonify(ret.to_dict()))


@app.route("/models/box", methods=['PUT'])
def put_box() -> RespT:
    """Add or update box.
        ---
        put:
            tags:
                - Models
            description: Add or update service type.
            requestBody:
                  content:
                    application/json:
                      schema:
                        $ref: Box
            responses:
                200:
                  description: Ok
    """

    box = object_type.Box.from_dict(convert_keys(request.json, camel_case_to_snake_case))
    BOXES[box.id] = box
    return "ok", 200


@app.route("/models/<string:id>/box", methods=['GET'])
def get_box(id: str) -> RespT:
    """Add or update box.
        ---
        get:
            tags:
                - Models
            summary: Gets ServiceType by service id.
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
                  content:
                    application/json:
                        schema:
                            $ref: Box
    """

    try:
        return cast(Response, jsonify(BOXES[id].to_dict()))
    except KeyError:
        return "Not found", 404


@app.route("/models/box", methods=['PUT'])
def put_cylinder() -> RespT:
    """Add or update box.
        ---
        put:
            tags:
                - Models
            description: Add or update service type.
            requestBody:
                  content:
                    application/json:
                      schema:
                        $ref: Cylinder
            responses:
                200:
                  description: Ok
    """

    cylinder = object_type.Cylinder.from_dict(convert_keys(request.json, camel_case_to_snake_case))
    CYLINDERS[cylinder.id] = cylinder
    return "ok", 200


@app.route("/models/<string:id>/cylinder", methods=['GET'])
def get_cylinder(id: str) -> RespT:
    """Add or update box.
        ---
        get:
            tags:
                - Models
            summary: Gets ServiceType by service id.
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
                  content:
                    application/json:
                        schema:
                            $ref: Cylinder
    """

    try:
        return cast(Response, jsonify(CYLINDERS[id].to_dict()))
    except KeyError:
        return "Not found", 404


@app.route("/models/sphere", methods=['PUT'])
def put_sphere() -> RespT:
    """Add or update sphere.
        ---
        put:
            tags:
                - Models
            description: Add or update sphere.
            requestBody:
                  content:
                    application/json:
                      schema:
                        $ref: Sphere
            responses:
                200:
                  description: Ok
    """

    sphere = object_type.Sphere.from_dict(convert_keys(request.json, camel_case_to_snake_case))
    SPHERES[sphere.id] = sphere
    return "ok", 200


@app.route("/models/<string:id>/sphere", methods=['GET'])
def get_sphere(id: str) -> RespT:
    """Add or update sphere.
        ---
        get:
            tags:
                - Models
            summary: Gets sphere by id.
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
                  content:
                    application/json:
                        schema:
                            $ref: Sphere
    """

    try:
        return cast(Response, jsonify(SPHERES[id].to_dict()))
    except KeyError:
        return "Not found", 404


@app.route("/models/<string:id>", methods=['DELETE'])
def delete_model(id: str) -> RespT:
    """Deletes model.
        ---
        delete:
            tags:
                - Models
            summary: Deletes model.
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
    """

    try:
        del BOXES[id]
    except KeyError:
        try:
            del CYLINDERS[id]
        except KeyError:
            try:
                del SPHERES[id]
            except KeyError:
                return "Not found", 404

    return "ok", 200


@app.route("/swagger/api/swagger.json", methods=["GET"])
def get_swagger() -> str:
    return json.dumps(spec.to_dict())


spec.components.schema(common.Project.__name__, schema=common.Project)
spec.components.schema(common.Scene.__name__, schema=common.Scene)
spec.components.schema(common.IdDescList.__name__, schema=common.IdDescList)
spec.components.schema(object_type.ObjectType.__name__, schema=object_type.ObjectType)
spec.components.schema(object_type.Box.__name__, schema=object_type.Box)
spec.components.schema(object_type.Cylinder.__name__, schema=object_type.Cylinder)
spec.components.schema(object_type.Sphere.__name__, schema=object_type.Sphere)


with app.test_request_context():

    spec.path(view=put_project)
    spec.path(view=get_project)
    spec.path(view=delete_project)
    spec.path(view=get_projects)

    spec.path(view=put_scene)
    spec.path(view=get_scene)
    spec.path(view=delete_scene)
    spec.path(view=get_scenes)

    spec.path(view=put_object_type)
    spec.path(view=get_object_type)
    spec.path(view=delete_object_type)
    spec.path(view=get_object_types)

    spec.path(view=put_box)
    spec.path(view=get_box)
    spec.path(view=put_cylinder)
    spec.path(view=get_cylinder)
    spec.path(view=put_sphere)
    spec.path(view=get_sphere)
    spec.path(view=delete_model)


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
