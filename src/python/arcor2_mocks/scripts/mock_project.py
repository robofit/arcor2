#!/usr/bin/env python3

import argparse
from datetime import datetime, timezone
from io import BytesIO
from typing import Dict, List, Optional, Tuple

import humps
from flask import jsonify, request, send_file

from arcor2.data import common, object_type
from arcor2.flask import FlaskException, RespT, create_app, run_app
from arcor2.json import JsonType
from arcor2_mocks import PROJECT_PORT, PROJECT_SERVICE_NAME, version

app = create_app(__name__)

SCENES: Dict[str, common.Scene] = {}
PROJECTS: Dict[str, common.Project] = {}
OBJECT_TYPES: Dict[str, object_type.ObjectType] = {}

BOXES: Dict[str, object_type.Box] = {}
CYLINDERS: Dict[str, object_type.Cylinder] = {}
SPHERES: Dict[str, object_type.Sphere] = {}

MESHES: Dict[str, Tuple[BytesIO, Optional[str]]] = {}


@app.route("/models/<string:mesh_id>/mesh/file", methods=["PUT"])
def put_mesh_file(mesh_id: str) -> RespT:
    """Puts mesh file.
    ---
    put:
        description: Puts mesh file.
        tags:
           - Models
        parameters:
            - name: mesh_id
              in: path
              description: unique ID
              required: true
              schema:
                type: string
        requestBody:
              content:
                multipart/form-data:
                  schema:
                    type: object
                    required:
                        - file
                    properties:
                      file:
                        type: string
                        format: binary
        responses:
            200:
              description: Ok
    """

    buff = BytesIO()
    fs = request.files["file"]
    fs.save(buff)
    MESHES[mesh_id] = buff, fs.filename
    return jsonify("ok"), 200


@app.route("/models/<string:mesh_id>/mesh/file", methods=["GET"])
def get_mesh_file(mesh_id: str) -> RespT:
    """Gets mesh file by id.
    ---
    get:
        tags:
            - Models
        summary: Gets mesh file by id.
        parameters:
            - name: mesh_id
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
                        type: string
                        format: binary
    """

    mesh_file, filename = MESHES[mesh_id]
    mesh_file.seek(0)
    return send_file(mesh_file, as_attachment=True, cache_timeout=0, attachment_filename=filename)


@app.route("/project", methods=["PUT"])
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

    project = common.Project.from_dict(humps.decamelize(request.json))
    project.modified = datetime.now(tz=timezone.utc)
    project.int_modified = None

    if project.id not in PROJECTS:
        project.created = project.modified

    PROJECTS[project.id] = project
    return jsonify(project.modified.isoformat())


@app.route("/project/<string:id>", methods=["GET"])
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
        return jsonify(PROJECTS[id].to_dict())
    except KeyError:
        return jsonify("Not found"), 404


@app.route("/project/<string:id>", methods=["DELETE"])
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
        return jsonify("Not found"), 404

    return jsonify("ok"), 200


@app.route("/projects", methods=["GET"])
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
                    type: array
                    items:
                      $ref: IdDesc
    """

    ret: List[JsonType] = []

    for proj in PROJECTS.values():
        assert proj.created
        assert proj.modified
        ret.append(common.IdDesc(proj.id, proj.name, proj.created, proj.modified, proj.description).to_dict())

    return jsonify(ret)


@app.route("/scene", methods=["PUT"])
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

    scene = common.Scene.from_dict(humps.decamelize(request.json))
    scene.modified = datetime.now(tz=timezone.utc)
    scene.int_modified = None

    if scene.id not in SCENES:
        scene.created = scene.modified

    SCENES[scene.id] = scene
    return jsonify(scene.modified.isoformat())


@app.route("/scene/<string:id>", methods=["GET"])
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
        return jsonify(SCENES[id].to_dict())
    except KeyError:
        return jsonify("Not found"), 404


@app.route("/scene/<string:id>", methods=["DELETE"])
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
        return jsonify("Not found"), 404

    return jsonify("ok"), 200


@app.route("/scenes", methods=["GET"])
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
                    type: array
                    items:
                      $ref: IdDesc
    """

    ret: List[JsonType] = []

    for scene in SCENES.values():
        assert scene.created
        assert scene.modified
        ret.append(common.IdDesc(scene.id, scene.name, scene.created, scene.modified, scene.description).to_dict())

    return jsonify(ret)


@app.route("/object_type", methods=["PUT"])
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

    obj_type = object_type.ObjectType.from_dict(humps.decamelize(request.json))
    obj_type.modified = datetime.now(tz=timezone.utc)

    if obj_type.id not in OBJECT_TYPES:
        obj_type.created = obj_type.modified

    OBJECT_TYPES[obj_type.id] = obj_type
    return jsonify(obj_type.modified.isoformat()), 200


@app.route("/object_types/<string:id>", methods=["GET"])
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
        return jsonify(OBJECT_TYPES[id].to_dict())
    except KeyError:
        return jsonify("Not found"), 404


@app.route("/object_type/<string:id>", methods=["DELETE"])
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
        return jsonify("Not found"), 404

    return jsonify("ok"), 200


@app.route("/object_types", methods=["GET"])
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
                    type: array
                    items:
                      $ref: IdDesc
    """

    ret: List[JsonType] = []

    for obj_type in OBJECT_TYPES.values():
        assert obj_type.created
        assert obj_type.modified
        ret.append(common.IdDesc(obj_type.id, "", obj_type.created, obj_type.modified, obj_type.description).to_dict())

    return jsonify(ret)


@app.route("/models/box", methods=["PUT"])
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

    if not isinstance(request.json, dict):
        raise FlaskException("Body should be a JSON dict containing Box.", error_code=400)

    # box = object_type.Box.from_dict(humps.decamelize(request.json))  # TODO disabled because of bug in pyhumps
    box = object_type.Box(request.json["id"], request.json["sizeX"], request.json["sizeY"], request.json["sizeZ"])
    BOXES[box.id] = box
    return jsonify("ok"), 200


@app.route("/models/<string:id>/box", methods=["GET"])
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
        return jsonify(BOXES[id].to_dict())
    except KeyError:
        return jsonify("Not found"), 404


@app.route("/models/cylinder", methods=["PUT"])
def put_cylinder() -> RespT:
    """Add or update cylinder.
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

    cylinder = object_type.Cylinder.from_dict(humps.decamelize(request.json))
    CYLINDERS[cylinder.id] = cylinder
    return jsonify("ok"), 200


@app.route("/models/<string:id>/cylinder", methods=["GET"])
def get_cylinder(id: str) -> RespT:
    """Add or update cylinder.
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
        return jsonify(CYLINDERS[id].to_dict())
    except KeyError:
        return jsonify("Not found"), 404


@app.route("/models/sphere", methods=["PUT"])
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

    sphere = object_type.Sphere.from_dict(humps.decamelize(request.json))
    SPHERES[sphere.id] = sphere
    return jsonify("ok"), 200


@app.route("/models/<string:id>/sphere", methods=["GET"])
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
        return jsonify(SPHERES[id].to_dict())
    except KeyError:
        return jsonify("Not found"), 404


@app.route("/models/<string:id>", methods=["DELETE"])
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
                return jsonify("Not found"), 404

    return jsonify("ok"), 200


def main() -> None:

    parser = argparse.ArgumentParser(description=PROJECT_SERVICE_NAME)
    parser.add_argument("-s", "--swagger", action="store_true", default=False)
    args = parser.parse_args()

    run_app(
        app,
        PROJECT_SERVICE_NAME,
        version(),
        "0.4.0",
        PROJECT_PORT,
        [
            common.Project,
            common.Scene,
            common.IdDesc,
            object_type.ObjectType,
            object_type.Box,
            object_type.Cylinder,
            object_type.Sphere,
        ],
        args.swagger,
    )


if __name__ == "__main__":
    main()
