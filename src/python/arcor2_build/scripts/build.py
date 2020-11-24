#!/usr/bin/env python3

import argparse
import json
import logging
import os
import zipfile
from datetime import datetime, timezone
from io import BytesIO
from typing import Set, Tuple, Union

import humps
from apispec import APISpec
from apispec_webframeworks.flask import FlaskPlugin
from flask import Flask, Response, request, send_file
from flask_cors import CORS
from flask_swagger_ui import get_swaggerui_blueprint

import arcor2_build
from arcor2.cached import CachedProject, CachedScene
from arcor2.clients import persistent_storage as ps
from arcor2.data.execution import PackageMeta
from arcor2.data.object_type import ObjectModel, ObjectType
from arcor2.exceptions import Arcor2Exception
from arcor2.helpers import port_from_url
from arcor2.logging import get_logger
from arcor2.object_types.utils import base_from_source, built_in_types_names
from arcor2.source import SourceException
from arcor2.source.utils import parse
from arcor2_build.source.logic import program_src
from arcor2_build.source.utils import derived_resources_class, global_action_points_class, global_actions_class
from arcor2_build_data import SERVICE_NAME, URL

logger = get_logger("Build")

# Create an APISpec
spec = APISpec(
    title=SERVICE_NAME,
    version=arcor2_build.version(),
    openapi_version="3.0.2",
    plugins=[FlaskPlugin()],
)

app = Flask(__name__)
CORS(app)

RETURN_TYPE = Union[Tuple[str, int], Response]


def get_base(
    object_types: Set[str], written_types: Set[str], obj_type: ObjectType, zf: zipfile.ZipFile, ot_path: str
) -> None:

    base = base_from_source(obj_type.source, obj_type.id)

    if not base:
        return

    if base in written_types:
        return

    if base not in object_types and base not in built_in_types_names():

        logger.debug(f"Getting {base} as base of {obj_type.id}.")
        base_obj_type = ps.get_object_type(base)

        zf.writestr(os.path.join(ot_path, humps.depascalize(base_obj_type.id)) + ".py", base_obj_type.source)
        object_types.add(base)
        written_types.add(base)

        # try to get base of the base
        get_base(object_types, written_types, base_obj_type, zf, ot_path)


def _publish(project_id: str, package_name: str) -> RETURN_TYPE:

    mem_zip = BytesIO()

    logger.debug(f"Generating package {package_name} for project_id: {project_id}.")

    with zipfile.ZipFile(mem_zip, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:

        try:
            logger.debug("Getting scene and project.")
            project = ps.get_project(project_id)
            cached_project = CachedProject(project)
            scene = ps.get_scene(project.scene_id)
            cached_scene = CachedScene(scene)

            data_path = "data"
            ot_path = "object_types"

            zf.writestr(os.path.join(ot_path, "__init__.py"), "")
            zf.writestr(os.path.join(data_path, "project.json"), project.to_json())
            zf.writestr(os.path.join(data_path, "scene.json"), scene.to_json())

            obj_types = set(cached_scene.object_types)
            obj_types_with_models: Set[str] = set()
            written_types: Set[str] = set()

            for scene_obj in scene.objects:

                if scene_obj.type in written_types:
                    continue

                logger.debug(f"Getting scene object type {scene_obj.type}.")
                obj_type = ps.get_object_type(scene_obj.type)

                if obj_type.model and obj_type.id not in obj_types_with_models:
                    obj_types_with_models.add(obj_type.id)

                    model = ps.get_model(obj_type.model.id, obj_type.model.type)
                    obj_model = ObjectModel(obj_type.model.type, **{model.type().value.lower(): model})  # type: ignore

                    zf.writestr(
                        os.path.join(data_path, "models", humps.depascalize(obj_type.id) + ".json"), obj_model.to_json()
                    )

                zf.writestr(os.path.join(ot_path, humps.depascalize(obj_type.id)) + ".py", obj_type.source)
                written_types.add(scene_obj.type)

                # handle inheritance
                get_base(obj_types, written_types, obj_type, zf, ot_path)

        except Arcor2Exception as e:
            logger.exception("Failed to get something from the project service.")
            return str(e), 404

        script_path = "script.py"

        try:

            if project.has_logic:
                logger.debug("Generating script from project logic.")
                zf.writestr(script_path, program_src(cached_project, cached_scene, built_in_types_names(), True))
            else:
                try:
                    logger.debug("Getting project sources.")
                    script = ps.get_project_sources(project.id).script

                    # check if it is a valid Python code
                    try:
                        parse(script)
                    except SourceException:
                        logger.exception("Failed to parse code of the uploaded script.")
                        return "Invalid code.", 501

                    zf.writestr(script_path, script)

                except ps.ProjectServiceException:

                    logger.info("Script not found on project service, creating one from scratch.")

                    # write script without the main loop
                    zf.writestr(script_path, program_src(cached_project, cached_scene, built_in_types_names(), False))

            logger.debug("Generating supplementary files.")

            logger.debug("resources.py")
            zf.writestr("resources.py", derived_resources_class(cached_project))

            logger.debug("actions.py")
            zf.writestr("actions.py", global_actions_class(cached_project))

            logger.debug("action_points.py")
            zf.writestr("action_points.py", global_action_points_class(cached_project))

            logger.debug("package.json")
            zf.writestr("package.json", PackageMeta(package_name, datetime.now(tz=timezone.utc)).to_json())

        except Arcor2Exception as e:
            logger.exception("Failed to generate script.")
            return str(e), 501

    logger.debug("Execution package finished.")
    mem_zip.seek(0)
    return send_file(mem_zip, as_attachment=True, cache_timeout=0, attachment_filename="arcor2_project.zip")


@app.route("/project/<string:project_id>/publish", methods=["GET"])
def project_publish(project_id: str) -> RETURN_TYPE:
    """Publish project
    ---
    get:
      description: Get zip file with execution package. To be used by the Execution service.
      parameters:
        - in: path
          name: project_id
          schema:
            type: string
          required: true
          description: unique ID
        - in: query
          name: packageName
          schema:
            type: string
            default: N/A
          required: false
          description: Package name
      responses:
        200:
          description: Ok
          content:
            application/zip:
                schema:
                  type: string
                  format: binary
                  example: The archive of execution package (.zip)
        404:
            description: Project ID or some of the required items was not found.
        501:
            description: Project invalid.
    """

    return _publish(project_id, request.args.get("packageName", default="N/A"))


@app.route("/project/<string:project_id>/script", methods=["PUT"])
def project_script(project_id: str):
    """Project script
    ---
    put:
      description: Add or update project main script (DOES NOT WORK YET).
      parameters:
        - in: path
          name: project_id
          schema:
            type: string
          required: true
          description: unique ID
      requestBody:
          content:
            text/x-python:
              schema:
                type: string
                format: binary
      responses:
        200:
          description: Ok
    """
    # TODO use get_logic_from_source
    pass


@app.route("/swagger/api/swagger.json", methods=["GET"])
def get_swagger() -> str:
    return json.dumps(spec.to_dict())


with app.test_request_context():
    spec.path(view=project_publish)
    spec.path(view=project_script)


def main() -> None:

    parser = argparse.ArgumentParser(description=SERVICE_NAME)
    parser.add_argument("-s", "--swagger", action="store_true", default=False)
    parser.add_argument(
        "-d",
        "--debug",
        help="Set logging level to debug.",
        action="store_const",
        const=logging.DEBUG,
        default=logging.INFO,
    )

    args = parser.parse_args()
    logger.setLevel(args.debug)

    if args.swagger:
        print(spec.to_yaml())
        return

    SWAGGER_URL = "/swagger"

    swaggerui_blueprint = get_swaggerui_blueprint(
        SWAGGER_URL, "./api/swagger.json"  # Swagger UI static files will be mapped to '{SWAGGER_URL}/dist/'
    )

    # Register blueprint at URL
    app.register_blueprint(swaggerui_blueprint, url_prefix=SWAGGER_URL)

    app.run(host="0.0.0.0", port=port_from_url(URL))


if __name__ == "__main__":
    main()
