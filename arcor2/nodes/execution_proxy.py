#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import base64
import json
import os
import shutil
import tempfile
import uuid
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from queue import Queue
from threading import Thread
from typing import Dict, List, Optional, TYPE_CHECKING, Tuple, Union

from apispec import APISpec  # type: ignore

from apispec_webframeworks.flask import FlaskPlugin  # type: ignore

from dataclasses_jsonschema import JsonSchemaMixin
from dataclasses_jsonschema.apispec import DataclassesPlugin

from flask import Flask, Response, jsonify, request, send_file

from flask_cors import CORS  # type: ignore

from flask_swagger_ui import get_swaggerui_blueprint  # type: ignore

import websocket  # type: ignore

from werkzeug.utils import secure_filename

import arcor2
from arcor2.data import common, events, execution, rpc
from arcor2.data.helpers import EVENT_MAPPING, RPC_MAPPING
from arcor2.nodes.execution import PORT as MANAGER_PORT
from arcor2.settings import PROJECT_PATH

PORT = int(os.getenv("ARCOR2_EXECUTION_PROXY_PORT", 5009))
SERVICE_NAME = "ARCOR2 Execution Service Proxy"


RespT = Union[Response, Tuple[str, int]]


class ExecutionState(Enum):

    Undefined: str = "Undefined"
    Running: str = "Running"
    Completed: str = "Completed"
    Faulted: str = "Faulted"
    Paused: str = "Paused"


@dataclass
class SummaryPackage(JsonSchemaMixin):

    id: str
    name: Optional[str] = None
    projectId: Optional[str] = None
    created: Optional[datetime] = None
    executed: Optional[datetime] = None


@dataclass
class ExecutionInfo(JsonSchemaMixin):

    state: ExecutionState
    activePackageId: Optional[str] = None
    exceptionMessage: Optional[str] = None


# Create an APISpec
spec = APISpec(
    title=SERVICE_NAME,
    version=arcor2.version(),
    openapi_version="3.0.2",
    plugins=[FlaskPlugin(), DataclassesPlugin()],
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

package_state: Optional[common.PackageState] = None
package_info: Optional[execution.PackageInfo] = None
exception_message: Optional[str] = None


def ws_thread() -> None:

    global package_info
    global package_state
    global exception_message
    assert ws

    while True:

        data = json.loads(ws.recv())

        if "event" in data:

            evt = EVENT_MAPPING[data["event"]].from_dict(data)

            if isinstance(evt, events.PackageInfoEvent):
                package_info = evt.data
            elif isinstance(evt, events.PackageStateEvent):
                package_state = evt.data

                if package_state.state == common.PackageStateEnum.RUNNING:
                    exception_message = None

            elif isinstance(evt, events.ProjectExceptionEvent):
                exception_message = evt.data.message

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


@app.route("/packages/<string:packageId>", methods=['PUT'])
def put_package(packageId: str) -> RespT:  # noqa
    """Put package
        ---
        put:
            description: Upload/update execution package.
            tags:
               - Packages
            parameters:
                - in: path
                  name: packageId
                  schema:
                    type: string
                  required: true
                  description: unique ID
            requestBody:
                  content:
                    multipart/form-data:
                      schema:
                        type: object
                        required:
                            - executionPackage
                        properties:
                          # 'file' will be the field name in this multipart request
                          executionPackage:
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

    file = request.files['executionPackage']
    file_name = secure_filename(file.filename)

    with tempfile.TemporaryDirectory() as tmpdirname:
        file_path = os.path.join(tmpdirname, file_name)
        file.save(file_path)

        with open(file_path, "rb") as zip_file:
            b64_bytes = base64.b64encode(zip_file.read())
            b64_str = b64_bytes.decode()

    resp = call_rpc(rpc.execution.UploadPackageRequest(
        id=get_id(),
        args=rpc.execution.UploadPackageArgs(packageId, b64_str)))

    if resp.result:
        return "ok", 200
    else:
        return jsonify(resp.messages), 501


@app.route("/packages/<string:packageId>", methods=['GET'])
def get_package(packageId: str) -> RespT:  # noqa
    """Get execution package.
                ---
                get:
                  description: Get zip file with execution package.
                  tags:
                    - Packages
                  parameters:
                    - in: path
                      name: packageId
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

    package_path = os.path.join(PROJECT_PATH, packageId)

    if not os.path.exists(package_path):
        return "Not found", 404

    with tempfile.TemporaryDirectory() as tmpdirname:

        archive_path = os.path.join(tmpdirname, packageId)
        shutil.make_archive(archive_path, 'zip', package_path)

        return send_file(archive_path + ".zip", as_attachment=True, cache_timeout=0)


@app.route("/packages", methods=['GET'])
def get_packages() -> RespT:
    """Gets summary for all stored execution packages.
                ---
                get:
                  description: Summary.
                  tags:
                    - Packages
                  responses:
                    200:
                      description: Ok
                      content:
                        application/json:
                          schema:
                            type: array
                            items:
                              $ref: SummaryPackage
                """

    resp = call_rpc(rpc.execution.ListPackagesRequest(id=get_id()))
    assert isinstance(resp, rpc.execution.ListPackagesResponse)

    ret: List[Dict] = []

    for pck in resp.data:
        sp = SummaryPackage(pck.id)
        sp.name = pck.package_meta.name
        sp.created = pck.package_meta.built
        sp.projectId = pck.project_id
        sp.executed = pck.package_meta.executed
        ret.append(sp.to_dict())

    return jsonify(ret), 200


@app.route("/packages/<string:packageId>", methods=['DELETE'])
def delete_package(packageId: str) -> RespT:  # noqa
    """Delete package.
            ---
            delete:
              description: Delete package.
              tags:
                - Packages
              parameters:
                - in: path
                  name: packageId
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

    resp = call_rpc(rpc.execution.DeletePackageRequest(id=get_id(), args=rpc.common.IdArgs(id=packageId)))

    if resp.result:
        return "ok", 200
    else:
        return jsonify(resp.messages), 501


@app.route("/packages/<string:packageId>/start", methods=['PUT'])
def package_start(packageId: str) -> RespT:  # noqa
    """Run project
            ---
            put:
              description: Start execution of the execution package.
              tags:
                - Packages
              parameters:
                - in: path
                  name: packageId
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

    resp = call_rpc(rpc.execution.RunPackageRequest(id=get_id(), args=rpc.execution.RunPackageArgs(id=packageId)))

    if resp.result:
        return "ok", 200
    else:
        return jsonify(resp.messages), 501


@app.route("/packages/stop", methods=['PUT'])
def packages_stop() -> RespT:
    """Stops running project
            ---
            put:
              description: Stops execution of the given package.
              tags:
                - Packages
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
def packages_pause() -> RespT:
    """Pauses running package.
            ---
            put:
              description: Pause execution of the given package.
              tags:
                - Packages
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
def packages_resume() -> RespT:
    """Resumes running package.
            ---
            put:
              description: Resumes execution of the given package.
              tags:
                - Packages
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


@app.route("/packages/executioninfo", methods=['GET'])
def packages_executioninfo() -> RespT:
    """/packages/executioninfo
            ---
            get:
              description: /packages/executioninfo
              tags:
                - Packages
              responses:
                200:
                  description: Ok
                  content:
                    application/json:
                      schema:
                        $ref: ExecutionInfo
                404:
                    description: No project running
            """

    if package_state is None or package_state.state == common.PackageStateEnum.UNDEFINED:
        ret = ExecutionInfo(ExecutionState.Undefined)
    elif package_state.state == common.PackageStateEnum.RUNNING:
        ret = ExecutionInfo(ExecutionState.Running, package_state.package_id)
    elif package_state.state == common.PackageStateEnum.PAUSED:
        ret = ExecutionInfo(ExecutionState.Paused, package_state.package_id)
    elif package_state.state == common.PackageStateEnum.STOPPED:

        if exception_message:
            ret = ExecutionInfo(ExecutionState.Faulted, package_state.package_id, exception_message)
        else:
            ret = ExecutionInfo(ExecutionState.Completed, package_state.package_id)
    else:
        return "Unhandled state", 501

    return jsonify(ret.to_dict()), 200


@app.route("/swagger/api/swagger.json", methods=["GET"])
def get_swagger() -> str:
    return json.dumps(spec.to_dict())


spec.components.schema(SummaryPackage.__name__, schema=SummaryPackage)
spec.components.schema(ExecutionInfo.__name__, schema=ExecutionInfo)


with app.test_request_context():
    spec.path(view=put_package)
    spec.path(view=get_package)
    spec.path(view=get_packages)
    spec.path(view=delete_package)
    spec.path(view=package_start)
    spec.path(view=packages_stop)
    spec.path(view=packages_pause)
    spec.path(view=packages_resume)
    spec.path(view=packages_executioninfo)


def main() -> None:

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
