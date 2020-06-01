#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import base64
import json
import os
import shutil
import tempfile
import uuid
from queue import Queue
from typing import Dict, TYPE_CHECKING, Optional
from threading import Thread

import websocket  # type: ignore
from apispec import APISpec  # type: ignore
from apispec_webframeworks.flask import FlaskPlugin  # type: ignore
from flask import Flask, jsonify, request, send_file
from flask_cors import CORS  # type: ignore
from flask_swagger_ui import get_swaggerui_blueprint  # type: ignore
from werkzeug.utils import secure_filename

import arcor2
from arcor2.data import rpc, events, common, execution
from arcor2.data.helpers import RPC_MAPPING, EVENT_MAPPING
from arcor2.nodes.execution import PORT as MANAGER_PORT
from arcor2.settings import PROJECT_PATH

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
CORS(app)

ws: Optional[websocket.WebSocket] = None

if TYPE_CHECKING:
    ReqQueue = Queue[rpc.common.Request]  # this is only processed by mypy
    RespQueue = Queue[rpc.common.Response]
else:
    ReqQueue = Queue  # this is not seen by mypy but will be executed at runtime.
    RespQueue = Queue


rpc_request_queue: ReqQueue = ReqQueue()
rpc_responses: Dict[int, RespQueue] = {}

package_info: Optional[execution.PackageInfo] = None


def ws_thread():

    global package_info
    assert ws

    while True:

        data = json.loads(ws.recv())

        if "event" in data:

            evt = EVENT_MAPPING[data["event"]].from_dict(data)

            if isinstance(evt, events.PackageInfoEvent):
                package_info = evt.data
            elif isinstance(evt, events.PackageStateEvent):

                if evt.data.state == common.PackageStateEnum.STOPPED:
                    package_info = None

        elif "response" in data:
            resp = RPC_MAPPING[data["response"]][1].from_dict(data)
            rpc_responses[resp.id].put(resp)


def call_rpc(req: rpc.common.Request) -> rpc.common.Response:

    assert req.id not in rpc_responses
    assert ws

    rpc_responses[req.id] = RespQueue(maxsize=1)
    ws.send(req.to_json())
    resp = rpc_responses[req.id].get()
    del rpc_responses[req.id]
    return resp


def get_id() -> int:
    return uuid.uuid4().int


def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() == "zip"


@app.route("/packages/<string:package_id>", methods=['PUT'])
def put_package(package_id: str):
    """Put package
        ---
        put:
            description: Upload/update execution package.
            parameters:
                - in: path
                  name: package_id
                  schema:
                    type: string
                  required: true
                  description: unique ID
            requestBody:
                  content:
                    multipart/form-data:
                      schema:
                        type: object
                        properties:
                          # 'file' will be the field name in this multipart request
                          file:
                            type: string
                            format: binary
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

    file = request.files['file']
    file_name = secure_filename(file.filename)

    with tempfile.TemporaryDirectory() as tmpdirname:
        file_path = os.path.join(tmpdirname, file_name)
        file.save(file_path)

        with open(file_path, "rb") as zip_file:
            b64_bytes = base64.b64encode(zip_file.read())
            b64_str = b64_bytes.decode()

    resp = call_rpc(rpc.execution.UploadPackageRequest(
            id=get_id(),
            args=rpc.execution.UploadPackageArgs(package_id, b64_str)))

    if resp.result:
        return "ok", 200
    else:
        return jsonify(resp.messages), 501


@app.route("/packages/<string:package_id>", methods=['GET'])
def get_package(package_id: str):
    """Get execution package.
                ---
                get:
                  description: Get zip file with execution package.
                  parameters:
                    - in: path
                      name: package_id
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
                        description: Package ID was not found.
                """

    package_path = os.path.join(PROJECT_PATH, package_id)

    if not os.path.exists(package_path):
        return "Not found", 404

    with tempfile.TemporaryDirectory() as tmpdirname:

        archive_path = os.path.join(tmpdirname, package_id)
        shutil.make_archive(archive_path, 'zip', package_path)

        return send_file(archive_path + ".zip", as_attachment=True, cache_timeout=0)


# TODO use DataClassPlugin / PackageSummary model
@app.route("/packages", methods=['GET'])
def get_packages():
    """Gets summary for all stored execution packages.
                ---
                get:
                  description: Summary.
                  responses:
                    200:
                      description: Ok
                      content:
                        application/json:
                          schema:
                            type: array
                            items:
                              type: object
                              properties:
                                id:
                                  type: string
                                date_time:
                                  type: string
                                  format: date-time
                """

    resp = call_rpc(rpc.execution.ListPackagesRequest(id=get_id()))
    assert isinstance(resp, rpc.execution.ListPackagesResponse)

    return jsonify([d.to_dict() for d in resp.data]), 200


@app.route("/packages/<string:package_id>", methods=['DELETE'])
def delete_package(package_id: str):
    """Delete package.
            ---
            delete:
              description: Delete package.
              parameters:
                - in: path
                  name: package_id
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

    resp = call_rpc(rpc.execution.DeletePackageRequest(id=get_id(), args=rpc.common.IdArgs(id=package_id)))

    if resp.result:
        return "ok", 200
    else:
        return jsonify(resp.messages), 501


@app.route("/packages/<string:package_id>/start", methods=['PUT'])
def package_start(package_id: str):
    """Run project
            ---
            put:
              description: Start execution of the execution package.
              parameters:
                - in: path
                  name: package_id
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

    resp = call_rpc(rpc.execution.RunPackageRequest(id=get_id(), args=rpc.common.IdArgs(id=package_id)))

    if resp.result:
        return "ok", 200
    else:
        return jsonify(resp.messages), 501


@app.route("/packages/stop", methods=['PUT'])
def packages_stop():
    """Stops running project
            ---
            put:
              description: Stops execution of the given package.
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

    resp = call_rpc(rpc.execution.StopPackageRequest(id=get_id()))

    if resp.result:
        return "ok", 200
    else:
        return jsonify(resp.messages), 501


@app.route("/packages/pause", methods=['PUT'])
def packages_pause():
    """Pauses running package.
            ---
            put:
              description: Pause execution of the given package.
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

    resp = call_rpc(rpc.execution.PausePackageRequest(id=get_id()))

    if resp.result:
        return "ok", 200
    else:
        return jsonify(resp.messages), 501


@app.route("/packages/resume", methods=['PUT'])
def packages_resume():
    """Resumes running package.
            ---
            put:
              description: Resumes execution of the given package.
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

    resp = call_rpc(rpc.execution.ResumePackageRequest(id=get_id()))

    if resp.result:
        return "ok", 200
    else:
        return jsonify(resp.messages), 501


@app.route("/packages/active", methods=['GET'])
def packages_active():
    """Get id of the running package.
            ---
            get:
              description: Get id of the running package.
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

    if package_info:
        return package_info.package_id, 200
    else:
        return "No project running.", 404


@app.route("/swagger/api/swagger.json", methods=["GET"])
def get_swagger():
    return json.dumps(spec.to_dict())


with app.test_request_context():
    spec.path(view=put_package)
    spec.path(view=get_package)
    spec.path(view=get_packages)
    spec.path(view=delete_package)
    spec.path(view=package_start)
    spec.path(view=packages_stop)
    spec.path(view=packages_pause)
    spec.path(view=packages_resume)
    spec.path(view=packages_active)


def main():

    parser = argparse.ArgumentParser(description=SERVICE_NAME)
    parser.add_argument('-s', '--swagger', action="store_true", default=False)
    args = parser.parse_args()

    if args.swagger:
        print(spec.to_yaml())
        return

    global ws
    ws = websocket.create_connection(f"ws://0.0.0.0:{MANAGER_PORT}", enable_multithread=True)

    thread = Thread(target=ws_thread, daemon=True)
    thread.start()

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
