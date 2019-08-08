#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from typing import Union, Dict
import os
import json
import sys

from apispec import APISpec
from apispec_webframeworks.flask import FlaskPlugin
from flask import Flask, jsonify, request
from werkzeug.exceptions import NotFound, InternalServerError
from dataclasses_jsonschema import ValidationError
from dataclasses_jsonschema.apispec import DataclassesPlugin
from pymongo import MongoClient  # type: ignore

from arcor2.data import Scene, Project, IdDesc, IdDescList, ProjectSources, ObjectType

# Create an APISpec
spec = APISpec(
    title="ARCOR2 Persistent Storage",
    version="1.0.0",
    openapi_version="3.0.2",
    plugins=[FlaskPlugin(), DataclassesPlugin()],
)


# Dependant schemas are added automatically
spec.components.schema(IdDescList.__name__, schema=IdDescList)
spec.components.schema(Project.__name__, schema=Project)
spec.components.schema(ProjectSources.__name__, schema=ProjectSources)
spec.components.schema(Scene.__name__, schema=Scene)
spec.components.schema(ObjectType.__name__, schema=ObjectType)

try:
    MONGO_ADDRESS = os.environ["ARCOR2_MONGO_ADDRESS"]
    DB = MongoClient(f"mongodb://{MONGO_ADDRESS}").arcor2
except (ValueError, IndexError) as e:
    sys.exit("'ARCOR2_MONGO_ADDRESS' env. variable not well formated. Correct format is 'hostname:port'")
except KeyError:
    sys.exit("'ARCOR2_MONGO_ADDRESS' env. variable not set.")

app = Flask(__name__)

# app.config['APISPEC_SPEC'] = spec
# app.config['APISPEC_SWAGGER_URL'] = '/swagger/'


def get_data(data_cls, collection, obj_id):

    data: Union[None, Dict] = collection.find_one({'id': obj_id})

    if not data:
        raise NotFound(f"Item with id {obj_id} does not exist.")

    try:
        inst = data_cls.from_dict(data)
    except ValidationError as e:
        raise InternalServerError(f"Data invalid: {e}")

    return jsonify(inst.to_dict())


def add_or_update(data_cls, collection):

    body_data = request.get_json(force=True)

    try:
        req_inst = data_cls.from_dict(json.loads(body_data))
    except ValidationError as e:
        raise InternalServerError(f"Invalid data: {e}")

    assert req_inst.id

    data: Union[None, Dict] = collection.find_one({'id': req_inst.id})

    if not data:
        collection.insert_one(req_inst.to_dict())
        return jsonify(success=True, message="Added.")
    else:
        collection.replace_one({'id': req_inst.id}, req_inst.to_dict())
        return jsonify(success=True, message="Updated.")


@app.route("/projects", methods=['GET'])
def get_project_ids():
    """Lists projects
            ---
            get:
              description: Get list of projects
              responses:
                200:
                  description: Ok
                  content:
                    application/json:
                      schema: IdDescList
            """

    return get_ids(DB.projects)


@app.route("/scenes", methods=['GET'])
def get_scenes_ids():
    """Lists scenes
            ---
            get:
              description: Get list of scenes
              responses:
                200:
                  description: Ok
                  content:
                    application/json:
                      schema: IdDescList
            """

    return get_ids(DB.scenes)


@app.route("/object_types", methods=['GET'])
def get_object_types_ids():
    """Lists object types
            ---
            get:
              description: Get list of object type IDs
              responses:
                200:
                  description: Ok
                  content:
                    application/json:
                      schema: IdDescList
            """

    return get_ids(DB.object_types)


def get_ids(collection):

    ret = IdDescList()

    for doc in collection.find({}, {"id": 1, "desc": 1, "_id": False}):
        if doc:
            if "desc" not in doc:
                doc["desc"] = ""
            ret.items.append(IdDesc.from_dict(doc))

    return jsonify(ret.to_dict())


@app.route("/project/<string:project_id>/sources", methods=['GET'])
def get_project_sources(project_id):
    """Project Sources
            ---
            get:
              description: Get project sources by project ID
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
                    application/json:
                      schema: ProjectSources
            """

    return get_data(ProjectSources, DB.project_sources, project_id)


@app.route("/project/<string:project_id>", methods=['GET'])
def get_project(project_id):  # TODO jak tam dostat proste string misto StringIdParameter???
    """Project
        ---
        get:
          description: Get project by ID
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
                application/json:
                  schema: Project
        """

    return get_data(Project, DB.projects, project_id)


@app.route("/project", methods=['POST'])
def post_project():
    """Project
        ---
        post:
          description: Add or update project
          requestBody:
            description: Project data
            required: true
            content:
              application/json:
                schema: Project
          responses:
            200:
              description: Ok
        """

    return add_or_update(Project, DB.projects)


@app.route("/project/sources", methods=['POST'])
def post_project_sources():
    """Project sources
        ---
        post:
          description: Add or update project sources
          requestBody:
            description: Sources data
            required: true
            content:
              application/json:
                schema: ProjectSources
          responses:
            200:
              description: Ok
        """

    return add_or_update(ProjectSources, DB.project_sources)


@app.route("/scene", methods=['POST'])
def post_scene():
    """Scene
        ---
        post:
          description: Add or update scene
          requestBody:
            description: Scene data
            required: true
            content:
              application/json:
                schema: Scene
          responses:
            200:
              description: Ok
        """

    return add_or_update(Scene, DB.scenes)


@app.route("/scene/<string:scene_id>", methods=['GET'])
def get_scene(scene_id):
    """Scene
            ---
            get:
              description: Get scene by ID
              parameters:
                - in: path
                  name: scene_id
                  schema:
                    type: string
                  required: true
                  description: unique ID
              responses:
                200:
                  description: Ok
                  content:
                    application/json:
                      schema: Scene
            """

    return get_data(Scene, DB.scenes, scene_id)


@app.route("/object_type/<string:object_type_id>", methods=['GET'])
def get_object_type(object_type_id):
    """Scene
            ---
            get:
              description: Get object_type by ID
              parameters:
                - in: path
                  name: object_type_id
                  schema:
                    type: string
                  required: true
                  description: unique ID
              responses:
                200:
                  description: Ok
                  content:
                    application/json:
                      schema: ObjectType
            """

    return get_data(ObjectType, DB.object_types, object_type_id)


@app.route("/object_type", methods=['POST'])
def post_object_type():
    """Object Type
        ---
        post:
          description: Add or update object type
          requestBody:
            description: Object type data
            required: true
            content:
              application/json:
                schema: ObjectType
          responses:
            200:
              description: Ok
        """

    return add_or_update(ObjectType, DB.object_types)


with app.test_request_context():
    spec.path(view=get_project)
    spec.path(view=get_project_ids)
    spec.path(view=get_scene)
    spec.path(view=get_scenes_ids)
    spec.path(view=get_project_sources)
    spec.path(view=post_project)
    spec.path(view=post_scene)
    spec.path(view=get_object_type)
    spec.path(view=post_object_type)
    spec.path(view=post_project_sources)
    spec.path(view=get_object_types_ids)


def main():
    # print(spec.to_yaml())
    app.run(port=5001)

if __name__ == '__main__':
    main()
