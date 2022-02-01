#!/usr/bin/env python3

import argparse
from datetime import datetime, timezone
from io import BytesIO
from typing import Optional

import humps
from flask import jsonify, request, send_file

from arcor2.data import common, object_type
from arcor2.flask import FlaskException, Response, RespT, create_app, run_app
from arcor2.json import JsonType
from arcor2_mocks import PROJECT_PORT, PROJECT_SERVICE_NAME, version

app = create_app(__name__)

SCENES: dict[str, common.Scene] = {}
PROJECTS: dict[str, common.Project] = {}
OBJECT_TYPES: dict[str, object_type.ObjectType] = {}

BOXES: dict[str, object_type.Box] = {}
CYLINDERS: dict[str, object_type.Cylinder] = {}
SPHERES: dict[str, object_type.Sphere] = {}
MESHES: dict[str, object_type.Mesh] = {}

FILES: dict[str, tuple[BytesIO, Optional[str]]] = {}


# ----------------------------------------------------------------------------------------------------------------------


@app.route("/files/<string:fileId>", methods=["PUT"])
def put_file(fileId: str) -> RespT:
    """Puts file.
    ---
    put:
        description: Puts file.
        tags:
           - Files
        parameters:
            - name: fileId
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
            400:
              description: Invalid file id provided.
              content:
                application/json:
                  schema:
                    type: string
    """

    buff = BytesIO()
    fs = request.files["file"]
    fs.save(buff)
    FILES[fileId] = buff, fs.filename
    return Response(status=200)


@app.route("/files/<string:fileId>", methods=["GET"])
def get_file(fileId: str) -> RespT:
    """Gets file by id.
    ---
    get:
        tags:
            - Files
        summary: Gets file by id.
        parameters:
            - name: fileId
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

    file, filename = FILES[fileId]
    file.seek(0)
    return send_file(file, as_attachment=True, max_age=0, download_name=filename)


@app.route("/files", methods=["GET"])
def get_files() -> RespT:
    """Gets files ids.
    ---
    get:
        tags:
        - Files
        summary: Gets files ids.
        responses:
            200:
              description: Success
              content:
                application/json:
                  schema:
                    type: array
                    items:
                      type: string
    """

    return jsonify(list(FILES.keys()))


@app.route("/files/<string:fileId>", methods=["DELETE"])
def delete_file(fileId: str) -> RespT:
    """Deletes file.
    ---
    delete:
        tags:
            - Files
        summary: Deletes file.
        parameters:
            - name: fileId
              in: path
              description: unique ID
              required: true
              schema:
                type: string
        responses:
            200:
              description: Ok
            404:
              description: File not found.
              content:
                application/json:
                  schema:
                    type: string
    """

    try:
        del FILES[fileId]
    except KeyError:
        return jsonify("Not found"), 404

    return Response(status=200)


# ----------------------------------------------------------------------------------------------------------------------


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
              description: Timestamp of last project modification.
              content:
                application/json:
                  schema:
                    type: string
            404:
              description: Scene with specific id related to project not found.
              content:
                application/json:
                  schema:
                    $ref: WebApiError
    """

    if not isinstance(request.json, dict):
        raise FlaskException("Body should be a JSON dict containing Project.", error_code=400)

    project = common.Project.from_dict(humps.decamelize(request.json))

    if project.scene_id not in SCENES:
        return common.WebApiError(f"Scene {id} does not exist.", PROJECT_SERVICE_NAME).to_json(), 404

    project.modified = datetime.now(tz=timezone.utc)
    project.int_modified = None

    if project.id not in PROJECTS:
        project.created = project.modified
    else:
        project.created = PROJECTS[project.id].created

    PROJECTS[project.id] = project
    return jsonify(project.modified.isoformat())


@app.route("/projects/<string:id>", methods=["GET"])
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
            404:
              description: Project not found.
              content:
                application/json:
                  schema:
                    $ref: WebApiError
    """

    try:
        return jsonify(humps.camelize(PROJECTS[id].to_dict()))
    except KeyError:
        return common.WebApiError(f"Project {id} was not found.", PROJECT_SERVICE_NAME).to_json(), 404


@app.route("/projects/<string:id>", methods=["DELETE"])
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
            404:
              description: Project not found.
              content:
                application/json:
                  schema:
                    $ref: WebApiError
    """

    try:
        del PROJECTS[id]
    except KeyError:
        return common.WebApiError(f"Project {id} was not found.", PROJECT_SERVICE_NAME).to_json(), 404

    return Response(status=200)


@app.route("/projects", methods=["GET"])
def get_projects() -> RespT:
    """Add or update project.
    ---
    get:
        tags:
        - Project
        summary: Gets all projects id and description.
        responses:
            200:
              description: Success
              content:
                application/json:
                  schema:
                    type: array
                    items:
                      $ref: IdDesc
    """

    ret: list[JsonType] = []

    for proj in PROJECTS.values():
        assert proj.created
        assert proj.modified
        ret.append(
            humps.camelize(common.IdDesc(proj.id, proj.name, proj.created, proj.modified, proj.description).to_dict())
        )

    return jsonify(ret)


# ----------------------------------------------------------------------------------------------------------------------


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
              description: Timestamp of last scene modification.
              content:
                application/json:
                  schema:
                    type: string
                    format: date-time
            404:
              description: Object type with specific id related to putted scene not exist.
              content:
                application/json:
                  schema:
                    $ref: WebApiError
    """

    if not isinstance(request.json, dict):
        raise FlaskException("Body should be a JSON dict containing Scene.", error_code=400)

    scene = common.Scene.from_dict(humps.decamelize(request.json))

    for obj in scene.objects:
        if obj.type not in OBJECT_TYPES:
            return common.WebApiError(f"ObjectType {obj.type} does not exist.", PROJECT_SERVICE_NAME).to_json(), 404

    scene.modified = datetime.now(tz=timezone.utc)
    scene.int_modified = None

    if scene.id not in SCENES:
        scene.created = scene.modified
    else:
        scene.created = SCENES[scene.id].created

    SCENES[scene.id] = scene
    return jsonify(scene.modified.isoformat())


@app.route("/scenes/<string:id>", methods=["GET"])
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
            404:
              description: Scene not found.
              content:
                application/json:
                  schema:
                    $ref: WebApiError
    """

    try:
        return jsonify(humps.camelize(SCENES[id].to_dict()))
    except KeyError:
        return common.WebApiError(f"Scene {id} was not found.", PROJECT_SERVICE_NAME).to_json(), 404


@app.route("/scenes/<string:id>", methods=["DELETE"])
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
          404:
            description: Scene not found.
            content:
              application/json:
                schema:
                  $ref: WebApiError
    """

    try:
        del SCENES[id]
    except KeyError:
        return common.WebApiError(f"Scene {id} was not found.", PROJECT_SERVICE_NAME).to_json(), 404

    return Response(status=200)


@app.route("/scenes", methods=["GET"])
def get_scenes() -> RespT:
    """Add or update scene.
    ---
    get:
        tags:
        - Scene
        summary: Gets all scenes id and description.
        responses:
            200:
              description: Success
              content:
                application/json:
                  schema:
                    type: array
                    items:
                      $ref: IdDesc
    """

    ret: list[JsonType] = []

    for scene in SCENES.values():
        assert scene.created
        assert scene.modified
        ret.append(
            humps.camelize(
                common.IdDesc(scene.id, scene.name, scene.created, scene.modified, scene.description).to_dict()
            )
        )

    return jsonify(ret)


# ----------------------------------------------------------------------------------------------------------------------


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
              content:
                application/json:
                  schema:
                    type: string
                    format: date-time
    """

    if not isinstance(request.json, dict):
        raise FlaskException("Body should be a JSON dict containing ObjectType.", error_code=400)

    obj_type = object_type.ObjectType.from_dict(humps.decamelize(request.json))
    obj_type.modified = datetime.now(tz=timezone.utc)

    if obj_type.id not in OBJECT_TYPES:
        obj_type.created = obj_type.modified
    else:
        obj_type.created = OBJECT_TYPES[obj_type.id].created

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
          404:
            description: ObjectType not found.
            content:
              application/json:
                schema:
                  $ref: WebApiError
    """

    try:
        return jsonify(humps.camelize(OBJECT_TYPES[id].to_dict()))
    except KeyError:
        return common.WebApiError(f"ObjectType {id} was not found.", PROJECT_SERVICE_NAME).to_json(), 404


@app.route("/object_types/<string:id>", methods=["DELETE"])
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
            404:
              description: ObjectType not found.
              content:
                application/json:
                  schema:
                    $ref: WebApiError
    """

    try:
        del OBJECT_TYPES[id]
    except KeyError:
        return common.WebApiError(f"ObjectType {id} was not found.", PROJECT_SERVICE_NAME).to_json(), 404

    return Response(status=200)


@app.route("/object_types", methods=["GET"])
def get_object_types() -> RespT:
    """Add or update ObjectType.
    ---
    get:
        tags:
        - ObjectType
        summary: Gets all object types id and description.
        responses:
            200:
              description: Success
              content:
                application/json:
                  schema:
                    type: array
                    items:
                      $ref: IdDesc
    """

    ret: list[JsonType] = []

    for obj_type in OBJECT_TYPES.values():
        assert obj_type.created
        assert obj_type.modified
        ret.append(
            humps.camelize(
                common.IdDesc(obj_type.id, "", obj_type.created, obj_type.modified, obj_type.description).to_dict()
            )
        )

    return jsonify(ret)


# ----------------------------------------------------------------------------------------------------------------------


@app.route("/models", methods=["GET"])
def get_models() -> RespT:
    """Get all models.
    ---
    get:
        tags:
            - Models
        description: Get all models
        responses:
            200:
              description: Ok
              content:
                application/json:
                  schema:
                    type: array
                    items:
                      $ref: MetaModel3d
    """

    models: list[dict] = []

    for mod_type in (BOXES, CYLINDERS, SPHERES, MESHES):
        assert isinstance(mod_type, dict)
        for mod in mod_type.values():
            assert isinstance(mod, object_type.Model)
            models.append(mod.metamodel().to_dict())

    return jsonify(humps.camelize(models))


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

    box = object_type.Box.from_dict(humps.decamelize(request.json))
    BOXES[box.id] = box
    return Response(status=200)


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
            404:
              description: Model not found.
              content:
                application/json:
                  schema:
                    $ref: WebApiError
    """

    try:
        return jsonify(humps.camelize(BOXES[id].to_dict()))
    except KeyError:
        return common.WebApiError(f"Box {id} was not found.", PROJECT_SERVICE_NAME).to_json(), 404


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

    if not isinstance(request.json, dict):
        raise FlaskException("Body should be a JSON dict containing Cylinder.", error_code=400)

    cylinder = object_type.Cylinder.from_dict(humps.decamelize(request.json))
    CYLINDERS[cylinder.id] = cylinder
    return Response(status=200)


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
            404:
              description: Model not found.
              content:
                application/json:
                  schema:
                    $ref: WebApiError
    """

    try:
        return jsonify(humps.camelize(CYLINDERS[id].to_dict()))
    except KeyError:
        return common.WebApiError(f"Cylinder {id} was not found.", PROJECT_SERVICE_NAME).to_json(), 404


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

    if not isinstance(request.json, dict):
        raise FlaskException("Body should be a JSON dict containing Sphere.", error_code=400)

    sphere = object_type.Sphere.from_dict(humps.decamelize(request.json))
    SPHERES[sphere.id] = sphere
    return Response(status=200)


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
            404:
              description: Model not found.
              content:
                application/json:
                  schema:
                    $ref: WebApiError
    """

    try:
        return jsonify(humps.camelize(SPHERES[id].to_dict()))
    except KeyError:
        return common.WebApiError(f"Sphere {id} was not found.", PROJECT_SERVICE_NAME).to_json(), 404


@app.route("/models/mesh", methods=["PUT"])
def put_mesh() -> RespT:
    """Add or update mesh.
    ---
    put:
        tags:
            - Models
        description: Add or update mesh.
        requestBody:
              content:
                application/json:
                  schema:
                    $ref: Mesh
        responses:
            200:
              description: Ok
    """

    if not isinstance(request.json, dict):
        raise FlaskException("Body should be a JSON dict containing Mesh.", error_code=400)

    mesh = object_type.Mesh.from_dict(humps.decamelize(request.json))
    MESHES[mesh.id] = mesh
    return Response(status=200)


@app.route("/models/<string:id>/mesh", methods=["GET"])
def get_mesh(id: str) -> RespT:
    """Add or update mesh.
    ---
    get:
        tags:
            - Models
        summary: Gets mesh by id.
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
                        $ref: Mesh
            404:
              description: Model not found.
              content:
                application/json:
                  schema:
                    $ref: WebApiError
    """

    try:
        return jsonify(humps.camelize(MESHES[id].to_dict()))
    except KeyError:
        return common.WebApiError(f"Mesh {id} was not found.", PROJECT_SERVICE_NAME).to_json(), 404


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
            404:
              description: Not found.
              content:
                application/json:
                  schema:
                    $ref: WebApiError
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
                try:
                    del MESHES[id]
                except KeyError:
                    return common.WebApiError(f"Model {id} was not found.", PROJECT_SERVICE_NAME).to_json(), 404

    return Response(status=200)


# ----------------------------------------------------------------------------------------------------------------------


def main() -> None:

    parser = argparse.ArgumentParser(description=PROJECT_SERVICE_NAME)
    parser.add_argument("-s", "--swagger", action="store_true", default=False)
    args = parser.parse_args()

    run_app(
        app,
        PROJECT_SERVICE_NAME,
        version(),
        PROJECT_PORT,
        [
            common.Project,
            common.Scene,
            common.IdDesc,
            object_type.ObjectType,
            object_type.Box,
            object_type.Cylinder,
            object_type.Sphere,
            object_type.Mesh,
            common.WebApiError,
        ],
        args.swagger,
        api_version="0.16.0",
    )


if __name__ == "__main__":
    main()
