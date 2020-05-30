#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import json
import logging
import os
import shutil
import tempfile
from typing import Set
from datetime import datetime, timezone

import horast
from apispec import APISpec  # type: ignore
from apispec_webframeworks.flask import FlaskPlugin  # type: ignore
from flask import Flask, send_file, request
from flask_cors import CORS  # type: ignore
from flask_swagger_ui import get_swaggerui_blueprint  # type: ignore

import arcor2
from arcor2 import persistent_storage as ps
from arcor2.data.object_type import ObjectModel
from arcor2.data.execution import PackageMeta
from arcor2.helpers import camel_case_to_snake_case, logger_formatter
from arcor2.object_types_utils import built_in_types_names
from arcor2.source import SourceException
from arcor2.source.logic import program_src  # , get_logic_from_source
from arcor2.source.utils import derived_resources_class, global_action_points_class, global_actions_class

PORT = 5008
SERVICE_NAME = "ARCOR2 Build Service"

logger = logging.getLogger("build")
ch = logging.StreamHandler()
ch.setFormatter(logger_formatter())
logger.setLevel(logging.INFO)
logger.addHandler(ch)

# Create an APISpec
spec = APISpec(
    title=SERVICE_NAME,
    version=arcor2.version(),
    openapi_version="3.0.2",
    plugins=[FlaskPlugin()],
)

app = Flask(__name__)
CORS(app)


def _publish(project_id: str, package_name: str):

    with tempfile.TemporaryDirectory() as tmpdirname:

        try:
            project = ps.get_project(project_id)
            scene = ps.get_scene(project.scene_id)

            project_dir = os.path.join(tmpdirname, "arcor2_project")

            data_path = os.path.join(project_dir, "data")
            ot_path = os.path.join(project_dir, "object_types")
            srv_path = os.path.join(project_dir, "services")

            os.makedirs(data_path)
            os.makedirs(ot_path)
            os.makedirs(srv_path)

            with open(os.path.join(ot_path, "__init__.py"), "w"):
                pass

            with open(os.path.join(srv_path, "__init__.py"), "w"):
                pass

            with open(os.path.join(data_path, "project.json"), "w") as project_file:
                project_file.write(project.to_json())

            with open(os.path.join(data_path, "scene.json"), "w") as scene_file:
                scene_file.write(scene.to_json())

            obj_types_with_models: Set[str] = set()

            for scene_obj in scene.objects:  # TODO handle inheritance

                obj_type = ps.get_object_type(scene_obj.type)

                if obj_type.model and obj_type.id not in obj_types_with_models:
                    obj_types_with_models.add(obj_type.id)

                    model = ps.get_model(obj_type.model.id, obj_type.model.type)
                    obj_model = ObjectModel(obj_type.model.type, **{model.type().value.lower(): model})

                    with open(os.path.join(data_path, camel_case_to_snake_case(obj_type.id) + ".json"), "w")\
                            as model_file:
                        model_file.write(obj_model.to_json())

                with open(os.path.join(ot_path, camel_case_to_snake_case(obj_type.id)) + ".py", "w") as obj_file:
                    obj_file.write(obj_type.source)

            for scene_srv in scene.services:
                srv = ps.get_service_type(scene_srv.type)
                with open(os.path.join(srv_path, camel_case_to_snake_case(srv.id)) + ".py", "w") as srv_file:
                    srv_file.write(srv.source)

        except ps.PersistentStorageException as e:
            logger.exception("Failed to get something from the project service.")
            return str(e), 404

        try:

            with open(os.path.join(project_dir, 'script.py'), "w") as script_file:

                if project.has_logic:
                    script_file.write(program_src(project, scene, built_in_types_names(), True))
                else:
                    try:
                        script = ps.get_project_sources(project.id).script

                        # check if it is a valid Python code
                        try:
                            horast.parse(script)
                        except SyntaxError:
                            logger.exception("Failed to parse code of the uploaded script.")
                            return "Invalid code.", 501

                        script_file.write(script)

                    except ps.PersistentStorageException:

                        logger.info("Script not found on project service, creating one from scratch.")

                        # write script without the main loop
                        script_file.write(program_src(project, scene, built_in_types_names(), False))

            with open(os.path.join(project_dir, 'resources.py'), "w") as res:
                res.write(derived_resources_class(project))

            with open(os.path.join(project_dir, 'actions.py'), "w") as act:
                act.write(global_actions_class(project))

            with open(os.path.join(project_dir, 'action_points.py'), "w") as aps:
                aps.write(global_action_points_class(project))

            with open(os.path.join(project_dir, 'package.json'), "w") as pkg:
                pkg.write(PackageMeta(package_name, datetime.now(tz=timezone.utc)).to_json())

        except SourceException as e:
            logger.exception("Failed to generate script.")
            return str(e), 501

        archive_path = os.path.join(tmpdirname, "arcor2_project")
        shutil.make_archive(archive_path, 'zip',  project_dir)
        return send_file(archive_path + ".zip", as_attachment=True, cache_timeout=0)


@app.route("/project/<string:project_id>/publish", methods=['GET'])
def project_publish(project_id: str):
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
                  name: PackageName
                  schema:
                    type: string
                    default: Package
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

    return _publish(project_id, request.args.get('PackageName', default="N/A"))


@app.route("/project/<string:project_id>/script", methods=['PUT'])
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
def get_swagger():
    return json.dumps(spec.to_dict())


with app.test_request_context():
    spec.path(view=project_publish)
    spec.path(view=project_script)


def main():

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
