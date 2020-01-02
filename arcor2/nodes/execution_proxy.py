#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import json
import uuid

from apispec import APISpec  # type: ignore
from apispec_webframeworks.flask import FlaskPlugin  # type: ignore
from flask import Flask, jsonify
from flask_swagger_ui import get_swaggerui_blueprint  # type: ignore
import websocket  # type: ignore

import arcor2
from arcor2.data import rpc
from arcor2.nodes.manager import PORT as MANAGER_PORT

PORT = 5009
SERVICE_NAME = "ARCOR2 Execution Service Proxy"

# Create an APISpec
spec = APISpec(
    title=SERVICE_NAME,
    version=arcor2.version(),
    openapi_version="3.0.2",
    plugins=[FlaskPlugin()],
)

app = Flask(__name__)


# TODO find out why long-lasting connection is not possible (it is getting disconnected after few minutes)

class WebsocketContextManager:

    def __init__(self):
        self.ws = None

    def __enter__(self):
        self.ws = websocket.create_connection(f"ws://0.0.0.0:{MANAGER_PORT}")
        return self.ws

    def __exit__(self, ex_type, ex_value, traceback):
        self.ws.close()
        if ex_type:
            raise ex_type(ex_value)


def get_id() -> int:
    return uuid.uuid4().int


@app.route("/project/<string:project_id>/run", methods=['PUT'])
def project_run(project_id: str):
    """Run project
            ---
            put:
              description: Start execution of the project.
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
                501:
                    description: Contains array of errors.
                    content:
                      application/json:
                        schema:
                          type: array
                          items:
                            type: string
            """

    with WebsocketContextManager() as ws:

        ws.send(rpc.RunProjectRequest(id=get_id(), args=rpc.IdArgs(id=project_id)).to_json())  # type: ignore
        resp = rpc.RunProjectResponse.from_json(ws.recv())

        if resp.result:
            return 200
        else:
            return jsonify(resp.messages), 501


@app.route("/project/stop", methods=['PUT'])
def project_stop():
    """Stops running project
            ---
            put:
              description: Stops execution of the project.
              responses:
                200:
                  description: Ok
                501:
                    description: Contains array of errors.
                    content:
                      application/json:
                        schema:
                          type: array
                          items:
                            type: string
            """

    with WebsocketContextManager() as ws:

        ws.send(rpc.StopProjectRequest(id=get_id()).to_json())
        resp = rpc.RunProjectResponse.from_json(ws.recv())

        if resp.result:
            return 200
        else:
            return jsonify(resp.messages), 501


@app.route("/project/running", methods=['GET'])
def project_running():
    """Get id of the running project.
            ---
            get:
              description: Get id of the running project.
              responses:
                200:
                  description: Ok
                  content:
                    text/plain:
                      schema:
                        type: string
                        example: demo1
                404:
                    description: No project running
            """

    with WebsocketContextManager() as ws:

        ws.send(rpc.ProjectStateRequest(id=get_id()).to_json())
        resp = rpc.ProjectStateResponse.from_json(ws.recv())

        if resp.data.id:
            return resp.data.id, 200
        else:
            return "No project running.", 404


@app.route("/swagger/api/swagger.json", methods=["GET"])
def get_swagger():
    return json.dumps(spec.to_dict())


with app.test_request_context():
    spec.path(view=project_run)
    spec.path(view=project_stop)
    spec.path(view=project_running)


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
