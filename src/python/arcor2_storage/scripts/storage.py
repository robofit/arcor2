#!/usr/bin/env python3

from __future__ import annotations

import argparse
import copy
import mimetypes
from datetime import datetime, timezone
from io import BytesIO
from typing import Callable, Iterable, Type, TypeVar

import fastuuid as uuid
import humps
from dataclasses_jsonschema import JsonSchemaMixin
from flask import jsonify, request, send_file

from arcor2.data import common
from arcor2.data.common import IdDesc, Project, ProjectParameter, ProjectSources, Scene, SceneObjectOverride
from arcor2.data.object_type import Box, Cylinder, Mesh, MetaModel3d, Model, Model3dType, ObjectType, Sphere
from arcor2_storage import STORAGE_DB_PATH, STORAGE_PORT, STORAGE_SERVICE_NAME, version
from arcor2_storage.client import Asset
from arcor2_storage.exceptions import Argument, NotFound, ProjectGeneral, WebApiError
from arcor2_storage.storage import Database
from arcor2_web.flask import Response, RespT, create_app, run_app

Jsonable = TypeVar("Jsonable", bound=JsonSchemaMixin)
ParameterType = TypeVar("ParameterType", bound=JsonSchemaMixin)
ModelType = TypeVar("ModelType", bound=Model)

app = create_app(__name__)
db = Database(STORAGE_DB_PATH)


def _now() -> datetime:
    return datetime.now(tz=timezone.utc)


def _camelized(dc: Jsonable):
    return jsonify(humps.camelize(dc.to_dict()))


def _parse_payload(cls: Type[Jsonable], message: str) -> Jsonable:
    if not isinstance(request.json, dict):
        raise ProjectGeneral(message)

    return cls.from_dict(humps.decamelize(request.json))


def _param(name: str) -> str | None:
    return request.args.get(name) or request.args.get(humps.camelize(name))


def _touch_project(project_id: str, modified: datetime) -> None:
    project = db.get_project(project_id)

    if project is None:
        raise NotFound(f"Project {project_id} was not found.")

    project.modified = modified
    project.int_modified = None
    project.created = project.created or modified
    db.save_project(project)


# ----------------------------------------------------------------------------------------------------------------------
# Assets


@app.route("/assets", methods=["POST"])
def post_asset() -> RespT:
    """Upload or update asset binary.
    ---
    post:
        tags:
            - Assets
        description: Store asset file with optional id, description, and upsert flag.
        parameters:
            - name: id
              in: query
              description: Asset identifier. Generated when omitted.
              required: false
              schema:
                type: string
            - name: description
              in: query
              required: false
              schema:
                type: string
            - name: upsert
              in: query
              required: false
              schema:
                type: boolean
        requestBody:
            required: true
            content:
                multipart/form-data:
                    schema:
                        type: object
                        properties:
                            assetData:
                                type: string
                                format: binary
                        required:
                            - assetData
        responses:
            200:
                description: Stored asset metadata.
                content:
                    application/json:
                        schema:
                            $ref: Asset
            400:
                description: "Error types: **Argument**, **ProjectGeneral**."
                content:
                    application/json:
                        schema:
                            $ref: WebApiError
    """
    asset_id = request.args.get("id") or request.args.get("ID") or uuid.uuid4().hex
    description = request.args.get("description")
    upsert = request.args.get("upsert", "true").lower() == "true"

    file_storage = request.files.get("assetData")
    if not file_storage:
        raise Argument("Body should contain assetData.")

    buff = BytesIO()
    file_storage.save(buff)
    buff.seek(0)

    now = _now()
    existing = db.get_asset(asset_id)
    if existing and not upsert:
        raise Argument(f"Asset {asset_id} already exists.")

    created = existing.info.created if existing else now
    asset_info = Asset(asset_id, created, now, file_name=file_storage.filename, description=description)

    db.save_asset(asset_info, buff.getvalue(), replace=True)

    return _camelized(asset_info)


@app.route("/assets/info", methods=["GET"])
def get_assets() -> RespT:
    """List asset metadata.
    ---
    get:
        tags:
            - Assets
        responses:
            200:
                description: List of stored assets.
                content:
                    application/json:
                        schema:
                            type: array
                            items:
                                $ref: Asset
            500:
                description: "Error type: **ProjectGeneral**."
                content:
                    application/json:
                        schema:
                            $ref: WebApiError
    """
    infos = db.list_asset_info()
    return jsonify([humps.camelize(info.to_dict()) for info in infos])


@app.route("/assets/<string:asset_id>/exists", methods=["GET"])
def get_exists(asset_id: str) -> RespT:
    """Check if asset exists.
    ---
    get:
        tags:
            - Assets
        parameters:
            - name: asset_id
              in: path
              required: true
              schema:
                type: string
        responses:
            200:
                description: Existence flag.
                content:
                    application/json:
                        schema:
                            type: boolean
    """
    return jsonify(db.asset_exists(asset_id))


@app.route("/assets/<string:asset_id>", methods=["DELETE"])
def delete_asset(asset_id: str) -> RespT:
    """Delete asset.
    ---
    delete:
        tags:
            - Assets
        parameters:
            - name: asset_id
              in: path
              required: true
              schema:
                type: string
        responses:
            200:
                description: Asset deleted.
            404:
                description: "Error type: **NotFound**."
                content:
                    application/json:
                        schema:
                            $ref: WebApiError
    """
    if not db.delete_asset(asset_id):
        raise NotFound("Asset not found.")

    return Response(status=200)


@app.route("/assets/<string:asset_id>/data", methods=["GET"])
def get_asset_data(asset_id: str) -> RespT:
    """Download asset data.
    ---
    get:
        tags:
            - Assets
        parameters:
            - name: asset_id
              in: path
              required: true
              schema:
                type: string
        responses:
            200:
                description: Asset content.
                content:
                    application/octet-stream:
                        schema:
                            type: string
                            format: binary
            404:
                description: "Error type: **NotFound**."
                content:
                    application/json:
                        schema:
                            $ref: WebApiError
    """
    asset = db.get_asset(asset_id)

    if asset is None:
        raise NotFound("Asset not found.")

    content_type, _ = mimetypes.guess_type(asset.info.file_name or "")

    buff = BytesIO(asset.data)
    buff.seek(0)

    return send_file(
        buff,
        download_name=asset.info.file_name or asset.info.id,
        mimetype=content_type or "application/octet-stream",
        as_attachment=True,
    )


# ----------------------------------------------------------------------------------------------------------------------
# Projects


def _id_desc(values: Iterable[common.JsonSchemaMixin]) -> list[dict]:
    ret: list[dict] = []
    for item in values:
        assert isinstance(item, (Project, Scene, ObjectType))
        assert item.created
        assert item.modified
        ret.append(humps.camelize(IdDesc(item.id, item.name, item.created, item.modified, item.description).to_dict()))
    return ret


@app.route("/projects", methods=["PUT"])
def put_project() -> RespT:
    """Create or update project.
    ---
    put:
        tags:
            - Projects
        requestBody:
            required: true
            content:
                application/json:
                    schema:
                        $ref: Project
        responses:
            200:
                description: Modification timestamp.
                content:
                    application/json:
                        schema:
                            type: string
                            format: date-time
            404:
                description: "Error type: **NotFound** when scene does not exist."
                content:
                    application/json:
                        schema:
                            $ref: WebApiError
    """
    project = _parse_payload(Project, "Body should be a JSON dict containing Project.")

    if db.get_scene(project.scene_id) is None:
        raise NotFound(f"Scene {project.scene_id} does not exist.")

    now = _now()
    existing = db.get_project(project.id)

    project.modified = now
    project.int_modified = None
    project.created = existing.created if existing else now

    db.save_project(project)
    return jsonify(project.modified.isoformat())


@app.route("/projects/sources", methods=["PUT"])
def put_project_sources() -> RespT:
    """Upload project sources.
    ---
    put:
        tags:
            - Projects
        requestBody:
            required: true
            content:
                application/json:
                    schema:
                        $ref: ProjectSources
        responses:
            200:
                description: Sources saved.
            404:
                description: "Error type: **NotFound** when project is missing."
                content:
                    application/json:
                        schema:
                            $ref: WebApiError
    """
    project_sources = _parse_payload(ProjectSources, "Body should be a JSON dict containing ProjectSources.")

    if db.get_project(project_sources.id) is None:
        raise NotFound(f"Project {project_sources.id} does not exist.")

    db.save_project_sources(project_sources)
    return Response(status=200)


@app.route("/projects/<string:project_id>/sources", methods=["GET"])
def get_project_sources(project_id: str) -> RespT:
    """Get project sources.
    ---
    get:
        tags:
            - Projects
        parameters:
            - name: project_id
              in: path
              required: true
              schema:
                type: string
        responses:
            200:
                description: Project sources.
                content:
                    application/json:
                        schema:
                            $ref: ProjectSources
            404:
                description: "Error type: **NotFound**."
                content:
                    application/json:
                        schema:
                            $ref: WebApiError
    """
    project_sources = db.get_project_sources(project_id)

    if project_sources is None:
        raise NotFound(f"Sources for project {project_id} not found.")

    return _camelized(project_sources)


@app.route("/projects/<string:project_id>", methods=["GET"])
def get_project(project_id: str) -> RespT:
    """Get project.
    ---
    get:
        tags:
            - Projects
        parameters:
            - name: project_id
              in: path
              required: true
              schema:
                type: string
        responses:
            200:
                description: Project.
                content:
                    application/json:
                        schema:
                            $ref: Project
            404:
                description: "Error type: **NotFound**."
                content:
                    application/json:
                        schema:
                            $ref: WebApiError
    """
    project = db.get_project(project_id)

    if project is None:
        raise NotFound(f"Project {project_id} was not found.")

    return _camelized(project)


@app.route("/projects/<string:project_id>", methods=["DELETE"])
def delete_project(project_id: str) -> RespT:
    """Delete project.
    ---
    delete:
        tags:
            - Projects
        parameters:
            - name: project_id
              in: path
              required: true
              schema:
                type: string
        responses:
            200:
                description: Project deleted.
            404:
                description: "Error type: **NotFound**."
                content:
                    application/json:
                        schema:
                            $ref: WebApiError
    """
    if not db.delete_project(project_id):
        raise NotFound(f"Project {project_id} was not found.")

    return Response(status=200)


@app.route("/projects", methods=["GET"])
def get_projects() -> RespT:
    """List projects.
    ---
    get:
        tags:
            - Projects
        responses:
            200:
                description: Project summaries.
                content:
                    application/json:
                        schema:
                            type: array
                            items:
                                $ref: IdDesc
    """
    return jsonify(_id_desc(db.list_projects()))


@app.route("/projects/clone", methods=["PUT"])
def clone_project() -> RespT:
    """Clone existing project.
    ---
    put:
        tags:
            - Projects
        parameters:
            - name: project_id
              in: query
              required: true
              schema:
                type: string
            - name: new_project_name
              in: query
              required: true
              schema:
                type: string
            - name: new_project_id
              in: query
              required: false
              schema:
                type: string
            - name: new_description
              in: query
              required: false
              schema:
                type: string
        responses:
            200:
                description: Cloned project.
                content:
                    application/json:
                        schema:
                            $ref: Project
            400:
                description: "Error type: **Argument**."
                content:
                    application/json:
                        schema:
                            $ref: WebApiError
            404:
                description: "Error type: **NotFound**."
                content:
                    application/json:
                        schema:
                            $ref: WebApiError
    """
    project_id = _param("project_id")
    new_project_name = _param("new_project_name")

    if not project_id or not new_project_name:
        raise Argument("Parameters project_id and new_project_name are required.")

    new_project_id = _param("new_project_id") or Project.uid()
    new_description = _param("new_description")

    source = db.get_project(project_id)

    if source is None:
        raise NotFound(f"Project {project_id} was not found.")

    if db.get_project(new_project_id) is not None:
        raise Argument(f"Project {new_project_id} already exists.")

    cloned = copy.deepcopy(source)
    cloned.id = new_project_id
    cloned.name = new_project_name

    if new_description is not None:
        cloned.description = new_description

    now = _now()
    cloned.created = now
    cloned.modified = now
    cloned.int_modified = None

    db.save_project(cloned)
    project_params = db.get_project_parameters(project_id)
    if project_params:
        db.set_project_parameters(new_project_id, project_params, now)

    object_params = db.get_object_parameters(project_id)
    if object_params:
        db.set_object_parameters(new_project_id, object_params, now)

    source_code = db.get_project_sources(project_id)
    if source_code:
        db.save_project_sources(ProjectSources(new_project_id, source_code.script))

    return _camelized(cloned)


def _handle_parameters(
    project_id: str,
    parser: Callable[[dict], ParameterType],
    getter: Callable[[str], list[ParameterType]],
    setter: Callable[[str, list[ParameterType], datetime], None],
    *,
    return_timestamp: bool,
) -> RespT:
    payload = request.get_json(silent=True)

    if isinstance(payload, list):
        parameters = [parser(humps.decamelize(item)) for item in payload]
        now = _now()
        setter(project_id, parameters, now)
        _touch_project(project_id, now)

        if return_timestamp:
            return jsonify(now.isoformat())

        return Response(status=200)

    if db.get_project(project_id) is None:
        raise NotFound(f"Project {project_id} was not found.")

    params = getter(project_id)
    return jsonify([humps.camelize(param.to_dict()) for param in params])


@app.route("/projects/<string:project_id>/parameters", methods=["GET", "PUT"])
def project_parameters(project_id: str) -> RespT:
    """Get or set project parameters.
    ---
    get:
        tags:
            - Projects
        parameters:
            - name: project_id
              in: path
              required: true
              schema:
                type: string
        responses:
            200:
                description: Project parameters.
                content:
                    application/json:
                        schema:
                            type: array
                            items:
                                $ref: ProjectParameter
            404:
                description: "Error type: **NotFound**."
                content:
                    application/json:
                        schema:
                            $ref: WebApiError
    put:
        tags:
            - Projects
        parameters:
            - name: project_id
              in: path
              required: true
              schema:
                type: string
        requestBody:
            required: true
            content:
                application/json:
                    schema:
                        type: array
                        items:
                            $ref: ProjectParameter
        responses:
            200:
                description: Parameters updated timestamp.
                content:
                    application/json:
                        schema:
                            type: string
                            format: date-time
            404:
                description: "Error type: **NotFound**."
                content:
                    application/json:
                        schema:
                            $ref: WebApiError
    """
    return _handle_parameters(
        project_id,
        lambda item: ProjectParameter.from_dict(item),
        db.get_project_parameters,
        db.set_project_parameters,
        return_timestamp=True,
    )


@app.route("/projects/<string:project_id>/object-parameters", methods=["GET", "PUT"])
def object_parameters(project_id: str) -> RespT:
    """Get or set object parameters for project.
    ---
    get:
        tags:
            - Projects
        parameters:
            - name: project_id
              in: path
              required: true
              schema:
                type: string
        responses:
            200:
                description: Object parameter overrides.
                content:
                    application/json:
                        schema:
                            type: array
                            items:
                                $ref: SceneObjectOverride
            404:
                description: "Error type: **NotFound**."
                content:
                    application/json:
                        schema:
                            $ref: WebApiError
    put:
        tags:
            - Projects
        parameters:
            - name: project_id
              in: path
              required: true
              schema:
                type: string
        requestBody:
            required: true
            content:
                application/json:
                    schema:
                        type: array
                        items:
                            $ref: SceneObjectOverride
        responses:
            200:
                description: Parameters stored.
            404:
                description: "Error type: **NotFound**."
                content:
                    application/json:
                        schema:
                            $ref: WebApiError
    """
    return _handle_parameters(
        project_id,
        lambda item: SceneObjectOverride.from_dict(item),
        db.get_object_parameters,
        db.set_object_parameters,
        return_timestamp=False,
    )


# ----------------------------------------------------------------------------------------------------------------------
# Scenes


@app.route("/scenes", methods=["PUT"])
def put_scene() -> RespT:
    """Create or update scene.
    ---
    put:
        tags:
            - Scenes
        requestBody:
            required: true
            content:
                application/json:
                    schema:
                        $ref: Scene
        responses:
            200:
                description: Modification timestamp.
                content:
                    application/json:
                        schema:
                            type: string
                            format: date-time
            404:
                description: "Error type: **NotFound** when referenced ObjectType is missing."
                content:
                    application/json:
                        schema:
                            $ref: WebApiError
    """
    scene = _parse_payload(Scene, "Body should be a JSON dict containing Scene.")

    for obj in scene.objects:
        if obj.type not in db.object_type_ids():
            raise NotFound(f"ObjectType {obj.type} does not exist.")

    now = _now()
    existing = db.get_scene(scene.id)

    scene.modified = now
    scene.int_modified = None
    scene.created = existing.created if existing else now

    db.save_scene(scene)
    return jsonify(scene.modified.isoformat())


@app.route("/scenes/<string:scene_id>", methods=["GET"])
def get_scene(scene_id: str) -> RespT:
    """Get scene.
    ---
    get:
        tags:
            - Scenes
        parameters:
            - name: scene_id
              in: path
              required: true
              schema:
                type: string
        responses:
            200:
                description: Scene.
                content:
                    application/json:
                        schema:
                            $ref: Scene
            404:
                description: "Error type: **NotFound**."
                content:
                    application/json:
                        schema:
                            $ref: WebApiError
    """
    scene = db.get_scene(scene_id)

    if scene is None:
        raise NotFound(f"Scene {scene_id} was not found.")

    return _camelized(scene)


@app.route("/scenes/<string:scene_id>", methods=["DELETE"])
def delete_scene(scene_id: str) -> RespT:
    """Delete scene.
    ---
    delete:
        tags:
            - Scenes
        parameters:
            - name: scene_id
              in: path
              required: true
              schema:
                type: string
        responses:
            200:
                description: Scene deleted.
            404:
                description: "Error type: **NotFound**."
                content:
                    application/json:
                        schema:
                            $ref: WebApiError
    """
    if not db.delete_scene(scene_id):
        raise NotFound(f"Scene {scene_id} was not found.")

    return Response(status=200)


@app.route("/scenes", methods=["GET"])
def get_scenes() -> RespT:
    """List scenes.
    ---
    get:
        tags:
            - Scenes
        responses:
            200:
                description: Scene summaries.
                content:
                    application/json:
                        schema:
                            type: array
                            items:
                                $ref: IdDesc
    """
    return jsonify(_id_desc(db.list_scenes()))


# ----------------------------------------------------------------------------------------------------------------------
# Object types


@app.route("/object-types", methods=["PUT"])
def put_object_type() -> RespT:
    """Create or update object type.
    ---
    put:
        tags:
            - ObjectTypes
        requestBody:
            required: true
            content:
                application/json:
                    schema:
                        $ref: ObjectType
        responses:
            200:
                description: Modification timestamp.
                content:
                    application/json:
                        schema:
                            type: string
                            format: date-time
    """
    obj_type = _parse_payload(ObjectType, "Body should be a JSON dict containing ObjectType.")

    now = _now()
    existing = db.get_object_type(obj_type.id)

    obj_type.modified = now
    obj_type.created = existing.created if existing else now

    db.save_object_type(obj_type)
    return jsonify(obj_type.modified.isoformat())


@app.route("/object-types/<string:obj_type_id>", methods=["GET"])
def get_object_type(obj_type_id: str) -> RespT:
    """Get object type.
    ---
    get:
        tags:
            - ObjectTypes
        parameters:
            - name: obj_type_id
              in: path
              required: true
              schema:
                type: string
        responses:
            200:
                description: Object type.
                content:
                    application/json:
                        schema:
                            $ref: ObjectType
            404:
                description: "Error type: **NotFound**."
                content:
                    application/json:
                        schema:
                            $ref: WebApiError
    """
    obj_type = db.get_object_type(obj_type_id)

    if obj_type is None:
        raise NotFound(f"ObjectType {obj_type_id} was not found.")

    return _camelized(obj_type)


@app.route("/object-types/<string:obj_type_id>", methods=["DELETE"])
def delete_object_type(obj_type_id: str) -> RespT:
    """Delete object type.
    ---
    delete:
        tags:
            - ObjectTypes
        parameters:
            - name: obj_type_id
              in: path
              required: true
              schema:
                type: string
        responses:
            200:
                description: Object type deleted.
            404:
                description: "Error type: **NotFound**."
                content:
                    application/json:
                        schema:
                            $ref: WebApiError
    """
    if not db.delete_object_type(obj_type_id):
        raise NotFound(f"ObjectType {obj_type_id} was not found.")

    return Response(status=200)


@app.route("/object-types", methods=["GET"])
def get_object_types() -> RespT:
    """List object types.
    ---
    get:
        tags:
            - ObjectTypes
        responses:
            200:
                description: Object type summaries.
                content:
                    application/json:
                        schema:
                            type: array
                            items:
                                $ref: IdDesc
    """
    return jsonify(_id_desc(db.list_object_types()))


# ----------------------------------------------------------------------------------------------------------------------
# Models


def _model_from_request(model_cls: Type[ModelType]) -> ModelType:
    if not isinstance(request.json, dict):
        raise ProjectGeneral("Body should be a JSON dict containing model.")

    return model_cls.from_dict(humps.decamelize(request.json))


@app.route("/models", methods=["GET"])
def get_models() -> RespT:
    """List registered models.
    ---
    get:
        tags:
            - Models
        responses:
            200:
                description: Model metadata.
                content:
                    application/json:
                        schema:
                            type: array
                            items:
                                $ref: MetaModel3d
    """
    models = [model.metamodel().to_dict() for model in db.list_models()]
    return jsonify(humps.camelize(models))


@app.route("/models/<string:model_id>/<string:model_type>", methods=["GET"])
def get_model(model_id: str, model_type: str) -> RespT:
    """Get model of given type.
    ---
    get:
        tags:
            - Models
        parameters:
            - name: model_id
              in: path
              required: true
              schema:
                type: string
            - name: model_type
              in: path
              required: true
              schema:
                type: string
                enum: [box, cylinder, sphere, mesh]
        responses:
            200:
                description: Model instance.
                content:
                    application/json:
                        schema:
                            oneOf:
                                - $ref: "#/components/schemas/Box"
                                - $ref: "#/components/schemas/Cylinder"
                                - $ref: "#/components/schemas/Sphere"
                                - $ref: "#/components/schemas/Mesh"
            404:
                description: "Error type: **NotFound**."
                content:
                    application/json:
                        schema:
                            $ref: WebApiError
    """
    model = db.get_model(model_id)

    if model is None:
        raise NotFound(f"Model {model_id} was not found.")

    try:
        expected_type = Model3dType(model_type.capitalize())
    except ValueError as e:
        raise NotFound(f"Model type {model_type} is not supported.") from e

    if model.type() != expected_type:
        raise NotFound(f"Model {model_id} is not of type {expected_type.name}.")

    return _camelized(model)


@app.route("/models/meshes", methods=["GET"])
def get_meshes() -> RespT:
    """List meshes.
    ---
    get:
        tags:
            - Models
        responses:
            200:
                description: Mesh models.
                content:
                    application/json:
                        schema:
                            type: array
                            items:
                                $ref: Mesh
    """
    return jsonify([humps.camelize(mesh.to_dict()) for mesh in db.list_meshes()])


@app.route("/models/<string:model_id>", methods=["DELETE"])
def delete_model(model_id: str) -> RespT:
    """Delete model.
    ---
    delete:
        tags:
            - Models
        parameters:
            - name: model_id
              in: path
              required: true
              schema:
                type: string
        responses:
            200:
                description: Model deleted.
            404:
                description: "Error type: **NotFound**."
                content:
                    application/json:
                        schema:
                            $ref: WebApiError
    """
    if not db.delete_model(model_id):
        raise NotFound(f"Model {model_id} was not found.")

    return Response(status=200)


@app.route("/models/box", methods=["PUT"])
def put_box() -> RespT:
    """Create or update box model.
    ---
    put:
        tags:
            - Models
        requestBody:
            required: true
            content:
                application/json:
                    schema:
                        $ref: Box
        responses:
            200:
                description: Box stored.
    """
    box = _model_from_request(Box)
    db.save_model(box)
    return Response(status=200)


@app.route("/models/<string:model_id>/box", methods=["GET"])
def get_box(model_id: str) -> RespT:
    """Get box model.
    ---
    get:
        tags:
            - Models
        parameters:
            - name: model_id
              in: path
              required: true
              schema:
                type: string
        responses:
            200:
                description: Box model.
                content:
                    application/json:
                        schema:
                            $ref: Box
            404:
                description: "Error type: **NotFound**."
                content:
                    application/json:
                        schema:
                            $ref: WebApiError
    """
    model = db.get_model(model_id)

    if model is None or not isinstance(model, Box):
        raise NotFound(f"Box {model_id} was not found.")

    return _camelized(model)


@app.route("/models/cylinder", methods=["PUT"])
def put_cylinder() -> RespT:
    """Create or update cylinder model.
    ---
    put:
        tags:
            - Models
        requestBody:
            required: true
            content:
                application/json:
                    schema:
                        $ref: Cylinder
        responses:
            200:
                description: Cylinder stored.
    """
    cylinder = _model_from_request(Cylinder)
    db.save_model(cylinder)
    return Response(status=200)


@app.route("/models/<string:model_id>/cylinder", methods=["GET"])
def get_cylinder(model_id: str) -> RespT:
    """Get cylinder model.
    ---
    get:
        tags:
            - Models
        parameters:
            - name: model_id
              in: path
              required: true
              schema:
                type: string
        responses:
            200:
                description: Cylinder model.
                content:
                    application/json:
                        schema:
                            $ref: Cylinder
            404:
                description: "Error type: **NotFound**."
                content:
                    application/json:
                        schema:
                            $ref: WebApiError
    """
    model = db.get_model(model_id)

    if model is None or not isinstance(model, Cylinder):
        raise NotFound(f"Cylinder {model_id} was not found.")

    return _camelized(model)


@app.route("/models/sphere", methods=["PUT"])
def put_sphere() -> RespT:
    """Create or update sphere model.
    ---
    put:
        tags:
            - Models
        requestBody:
            required: true
            content:
                application/json:
                    schema:
                        $ref: Sphere
        responses:
            200:
                description: Sphere stored.
    """
    sphere = _model_from_request(Sphere)
    db.save_model(sphere)
    return Response(status=200)


@app.route("/models/<string:model_id>/sphere", methods=["GET"])
def get_sphere(model_id: str) -> RespT:
    """Get sphere model.
    ---
    get:
        tags:
            - Models
        parameters:
            - name: model_id
              in: path
              required: true
              schema:
                type: string
        responses:
            200:
                description: Sphere model.
                content:
                    application/json:
                        schema:
                            $ref: Sphere
            404:
                description: "Error type: **NotFound**."
                content:
                    application/json:
                        schema:
                            $ref: WebApiError
    """
    model = db.get_model(model_id)

    if model is None or not isinstance(model, Sphere):
        raise NotFound(f"Sphere {model_id} was not found.")

    return _camelized(model)


@app.route("/models/mesh", methods=["PUT"])
def put_mesh() -> RespT:
    """Create or update mesh model.
    ---
    put:
        tags:
            - Models
        requestBody:
            required: true
            content:
                application/json:
                    schema:
                        $ref: Mesh
        responses:
            200:
                description: Mesh stored.
    """
    mesh = _model_from_request(Mesh)
    db.save_model(mesh)
    return Response(status=200)


@app.route("/models/<string:model_id>/mesh", methods=["GET"])
def get_mesh(model_id: str) -> RespT:
    """Get mesh model.
    ---
    get:
        tags:
            - Models
        parameters:
            - name: model_id
              in: path
              required: true
              schema:
                type: string
        responses:
            200:
                description: Mesh model.
                content:
                    application/json:
                        schema:
                            $ref: Mesh
            404:
                description: "Error type: **NotFound**."
                content:
                    application/json:
                        schema:
                            $ref: WebApiError
    """
    model = db.get_model(model_id)

    if model is None or not isinstance(model, Mesh):
        raise NotFound(f"Mesh {model_id} was not found.")

    return _camelized(model)


# ----------------------------------------------------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(description=STORAGE_SERVICE_NAME)
    parser.add_argument("-s", "--swagger", action="store_true", default=False)
    args = parser.parse_args()

    run_app(
        app,
        STORAGE_SERVICE_NAME,
        version(),
        STORAGE_PORT,
        [
            Asset,
            common.Project,
            common.ProjectSources,
            common.Scene,
            common.IdDesc,
            common.ProjectParameter,
            common.SceneObjectOverride,
            ObjectType,
            Box,
            Cylinder,
            Sphere,
            Mesh,
            MetaModel3d,
            WebApiError,
        ],
        args.swagger,
        dependencies=None,
        api_version="2.0.0",
    )


if __name__ == "__main__":
    main()
