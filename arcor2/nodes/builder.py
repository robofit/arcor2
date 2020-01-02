#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import tempfile
import shutil
import argparse
import json

from typing import Set

from apispec import APISpec  # type: ignore
from apispec_webframeworks.flask import FlaskPlugin  # type: ignore
from flask import Flask, send_file
from flask_swagger_ui import get_swaggerui_blueprint  # type: ignore

import arcor2
from arcor2 import persistent_storage as ps
from arcor2.source.logic import program_src  # , get_logic_from_source
from arcor2.source.utils import derived_resources_class, global_actions_class
from arcor2.source import SourceException
from arcor2.object_types_utils import built_in_types_names
from arcor2.helpers import camel_case_to_snake_case
from arcor2.data.object_type import ObjectModel

PORT = 5007
SERVICE_NAME = "ARCOR2 Build Service"

# Create an APISpec
spec = APISpec(
    title=SERVICE_NAME,
    version=arcor2.version(),
    openapi_version="3.0.2",
    plugins=[FlaskPlugin()],
)

app = Flask(__name__)


@app.route("/project/<string:project_id>/publish", methods=['GET'])
def project_publish(project_id: str):
    """Publish project
            ---
            get:
              description: Get zip file with execution package
              parameters:
                - in: path
                  name: project_id
                  schema:
                    type: string
                  required: true
                  description: unique ID
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
                    obj_model = ObjectModel(obj_type.model.type, **{model.type().value: model})

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
            return str(e), 404

        try:

            with open(os.path.join(project_dir, 'script.py'), "w") as script:

                if not project.has_logic:
                    try:
                        # TODO check if script is valid somehow?
                        script.write(ps.get_project_sources(project.id).script)
                    except ps.PersistentStorageException:
                        # script not uploaded, write script with empty main loop
                        script.write(program_src(project, scene, built_in_types_names(), False))
                else:
                    script.write(program_src(project, scene, built_in_types_names(), True))

            with open(os.path.join(project_dir, 'resources.py'), "w") as res:
                res.write(derived_resources_class(project))

            with open(os.path.join(project_dir, 'actions.py'), "w") as act:
                act.write(global_actions_class(project))

        except SourceException as e:
            return str(e), 501

        archive_path = os.path.join(tmpdirname, "arcor2_project")
        shutil.make_archive(archive_path, 'zip',  project_dir)
        return send_file(archive_path + ".zip", as_attachment=True)


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
        f"./api/swagger.json"
    )

    # Register blueprint at URL
    app.register_blueprint(swaggerui_blueprint, url_prefix=SWAGGER_URL)

    app.run(host='0.0.0.0', port=PORT)


if __name__ == '__main__':
    main()
