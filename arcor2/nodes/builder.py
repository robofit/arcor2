#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import tempfile
import shutil

from apispec import APISpec
from apispec_webframeworks.flask import FlaskPlugin
from flask import Flask, jsonify, request, send_file
from werkzeug.exceptions import NotFound, InternalServerError
from dataclasses_jsonschema.apispec import DataclassesPlugin

from arcor2 import persistent_storage as ps
from arcor2.source.logic import program_src, get_logic_from_source
from arcor2.source.utils import derived_resources_class
from arcor2.source import SourceException
from arcor2.object_types_utils import built_in_types_names
from arcor2.helpers import camel_case_to_snake_case


# Create an APISpec
spec = APISpec(
    title="ARCOR2 Builder Service",
    version="0.0.1",
    openapi_version="3.0.2",
    plugins=[FlaskPlugin(), DataclassesPlugin()],
)

# Dependant schemas are added automatically
# spec.components.schema(IdDescList.__name__, schema=IdDescList)

app = Flask(__name__)

app.config['APISPEC_SPEC'] = spec
app.config['APISPEC_SWAGGER_URL'] = '/swagger/'


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
                500:
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

            with open(os.path.join(data_path, "project.json"), "w") as project_file:
                project_file.write(project.to_json())

            with open(os.path.join(data_path, "scene.json"), "w") as scene_file:
                scene_file.write(scene.to_json())

            for scene_obj in scene.objects:
                obj = ps.get_object_type(scene_obj.type)
                with open(os.path.join(ot_path, camel_case_to_snake_case(obj.id)), "w") as obj_file:
                    obj_file.write(obj.source)

            for scene_srv in scene.services:
                srv = ps.get_service_type(scene_srv.type)
                with open(os.path.join(srv_path, camel_case_to_snake_case(srv.id)), "w") as srv_file:
                    srv_file.write(srv.source)

        except ps.PersistentStorageException as e:
            print(e)
            return

        action_names = [act.id for obj in project.objects for aps in obj.action_points for act in aps.actions]

        try:

            with open('script.py', "w") as script:
                script.write(program_src(project, scene, built_in_types_names()))

            with open('resources.py', "w") as res:
                res.write(derived_resources_class(project.id, action_names))

        except SourceException as e:
            print(e)
            return

        archive_path = os.path.join(tmpdirname, "arcor2_project.zip")
        shutil.make_archive(archive_path, 'zip',  project_dir)
        return send_file(archive_path)


@app.route("/project/<string:project_id>/script", methods=['PUT'])
def project_script(project_id: str):
    """Project script
            ---
            put:
              description: Add or update project main script
              consumes:
                 - multipart/form-data
              parameters:
                 - in: formData
                   name: upfile
                   type: file
                   description: The file to upload.
              responses:
                200:
                  description: Ok
            """
    # TODO use get_logic_from_source
    pass


with app.test_request_context():
    spec.path(view=project_publish)


def main():
    print(spec.to_yaml())
    app.run(host='0.0.0.0', port=5007)


if __name__ == '__main__':
    main()
