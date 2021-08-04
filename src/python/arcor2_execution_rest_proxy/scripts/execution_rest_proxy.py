#!/usr/bin/env python3

import argparse
import base64
import os
import shutil
import tempfile
import time
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from queue import Queue
from threading import Thread
from typing import TYPE_CHECKING, Dict, List, Optional, Type

import arcor2_execution_rest_proxy
import websocket
from dataclasses_jsonschema import JsonSchemaMixin
from flask import Response, jsonify, request, send_file
from sqlitedict import SqliteDict
from werkzeug.utils import secure_filename

from arcor2 import json
from arcor2.data import events
from arcor2.data import rpc as arcor2_rpc
from arcor2.data.events import PackageInfo, PackageState, ProjectException
from arcor2.data.rpc import get_id
from arcor2.flask import RespT, create_app, run_app
from arcor2_execution_data import EVENTS, EXPOSED_RPCS
from arcor2_execution_data import URL as EXE_URL
from arcor2_execution_data import rpc
from arcor2_execution_data.package import PROJECT_PATH

PORT = int(os.getenv("ARCOR2_EXECUTION_PROXY_PORT", 5009))
SERVICE_NAME = "ARCOR2 Execution Service Proxy"

DB_PATH = os.getenv("ARCOR2_EXECUTION_PROXY_DB_PATH", "/tmp")  # should be directory where DBs can be stored
TOKENS_DB_PATH = os.path.join(DB_PATH, "tokens")


class ExecutionState(Enum):
    """Represents the state of package execution."""

    Undefined: str = "Undefined"
    Running: str = "Running"
    Completed: str = "Completed"
    Faulted: str = "Faulted"
    Paused: str = "Paused"
    Pending: str = "Pending"


@dataclass
class SummaryProject(JsonSchemaMixin):
    """Describes a project."""

    id: str
    name: str
    description: str


@dataclass
class SummaryPackage(JsonSchemaMixin):
    """Describes execution package."""

    id: str
    name: Optional[str] = None
    created: Optional[datetime] = None
    executed: Optional[datetime] = None
    project: Optional[SummaryProject] = None


@dataclass
class ExecutionInfo(JsonSchemaMixin):
    """Stores information about package execution."""

    state: ExecutionState
    activePackageId: Optional[str] = None
    exceptionMessage: Optional[str] = None


@dataclass
class Token(JsonSchemaMixin):
    """Describes Token."""

    id: str
    name: str
    access: bool = False


app = create_app(__name__)

ws: Optional[websocket.WebSocket] = None

if TYPE_CHECKING:
    ReqQueue = Queue[arcor2_rpc.common.RPC.Request]  # this is only processed by mypy
    RespQueue = Queue[arcor2_rpc.common.RPC.Response]
else:
    ReqQueue = Queue  # this is not seen by mypy but will be executed at runtime.
    RespQueue = Queue


rpc_request_queue: ReqQueue = ReqQueue()
rpc_responses: Dict[int, RespQueue] = {}

package_state: Optional[PackageState.Data] = None
package_info: Optional[PackageInfo.Data] = None
exception_messages: List[str] = []


@contextmanager
def tokens_db():
    """This is a wrapper for SqliteDict enabling one to change all settings at
    one place."""

    with SqliteDict(TOKENS_DB_PATH, autocommit=True, encode=json.dumps, decode=json.loads) as tokens:
        yield tokens


def ws_thread() -> None:  # TODO use (refactored) arserver client

    global package_info
    global package_state
    assert ws

    event_mapping: Dict[str, Type[events.Event]] = {evt.__name__: evt for evt in EVENTS}
    rpc_mapping: Dict[str, Type[arcor2_rpc.common.RPC]] = {rpc.__name__: rpc for rpc in EXPOSED_RPCS}

    while True:

        data = json.loads(ws.recv())  # TODO handle WebSocketConnectionClosedException

        if not isinstance(data, dict):
            continue

        if "event" in data:

            evt = event_mapping[data["event"]].from_dict(data)

            if isinstance(evt, PackageInfo):
                package_info = evt.data
            elif isinstance(evt, PackageState):
                package_state = evt.data

                if package_state.state == PackageState.Data.StateEnum.RUNNING:
                    exception_messages.clear()

            elif isinstance(evt, ProjectException):
                exception_messages.append(evt.data.message)

        elif "response" in data:
            resp = rpc_mapping[data["response"]].Response.from_dict(data)
            rpc_responses[resp.id].put(resp)


def call_rpc(req: arcor2_rpc.common.RPC.Request) -> arcor2_rpc.common.RPC.Response:

    assert req.id not in rpc_responses
    assert ws

    rpc_responses[req.id] = RespQueue(maxsize=1)

    ws.send(req.to_json())  # TODO handle WebSocketConnectionClosedException

    resp = rpc_responses[req.id].get()
    del rpc_responses[req.id]
    return resp


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() == "zip"


def package_exists(package_id: str) -> bool:
    return os.path.exists(os.path.join(PROJECT_PATH, package_id))


@app.route("/tokens/create", methods=["POST"])
def post_token() -> RespT:
    """post_token
    ---
    post:
        summary: Creates a token with the given name.
        operationId: CreateToken
        tags:
           - Tokens
        parameters:
            - in: query
              name: name
              schema:
                type: string
              required: true
              description: The name of the token.
        responses:
            200:
              description: Created token with requested name and execution access rights set to false.
              content:
                application/json:
                  schema:
                    $ref: Token
    """

    token = Token(uuid.uuid4().hex, request.args["name"])
    token_dict = token.to_dict()
    with tokens_db() as tokens:
        tokens[token.id] = token_dict

    return jsonify(token_dict), 200


@app.route("/tokens", methods=["GET"])
def get_tokens() -> RespT:
    """Get all known tokens.
    ---
    get:
      summary: Tokens.
      operationId: GetTokens
      tags:
        - Tokens
      responses:
        200:
          description: Array of all knows tokens.
          content:
            application/json:
              schema:
                type: array
                items:
                  $ref: Token
    """

    with tokens_db() as tokens:
        return jsonify(list(tokens.values())), 200


@app.route("/tokens/<string:tokenId>", methods=["DELETE"])
def delete_token(tokenId: str) -> RespT:  # noqa
    """Delete token.
    ---
    delete:
      summary: Remove given token from known tokens.
      operationId: RemoveToken
      tags:
        - Tokens
      parameters:
        - in: path
          name: tokenId
          schema:
            type: string
          required: true
          description: unique ID
      responses:
        200:
          description: Success
        404:
           description: Token not found
           content:
             application/json:
               schema:
                 type: string
    """

    with tokens_db() as tokens:
        try:
            del tokens[tokenId]
        except KeyError:
            return jsonify("Token not found"), 404

    return Response(status=200)


@app.route("/tokens/<string:tokenId>/access", methods=["PUT"])
def put_token_access(tokenId: str) -> RespT:  # noqa
    """put_token_access
    ---
    put:
        summary: Sets execution access rights for given token.
        operationId: SetAccess
        tags:
           - Tokens
        parameters:
            - in: path
              name: tokenId
              schema:
                type: string
              required: true
              description: Token Id to have access value changed.
            - in: query
              name: newAccess
              schema:
                type: boolean
              required: true
              description: New token access value.
        responses:
            200:
              description: Ok
            404:
              description: Token not found
              content:
                application/json:
                  schema:
                    type: string
    """

    with tokens_db() as tokens:
        try:
            token = Token.from_dict(tokens[tokenId])
        except KeyError:
            return jsonify("Token not found"), 404
        token.access = request.args["newAccess"] == "true"
        tokens[tokenId] = token.to_dict()

    return Response(status=200)


@app.route("/tokens/<string:tokenId>/access", methods=["GET"])
def get_token_access(tokenId: str) -> RespT:  # noqa
    """get_token_access
    ---
    get:
        summary: Gets execution access rights for given token.
        operationId: GetAccess
        tags:
           - Tokens
        parameters:
            - in: path
              name: tokenId
              schema:
                type: string
              required: true
              description: Token Id to be checked.
        responses:
            200:
              description: True if the given token has access rights, otherwise false.
              content:
                application/json:
                  schema:
                    type: boolean
            404:
              description: Token not found
              content:
                application/json:
                  schema:
                    type: string
    """

    with tokens_db() as tokens:
        try:
            token = Token.from_dict(tokens[tokenId])
        except KeyError:
            return jsonify("Token not found"), 404
        return jsonify(token.access), 200


@app.route("/packages/<string:packageId>", methods=["PUT"])
def put_package(packageId: str) -> RespT:  # noqa
    """Put package
    ---
    put:
        summary: Adds the execution package.
        operationId: PutPackage
        tags:
           - Packages
        parameters:
            - in: path
              name: packageId
              schema:
                type: string
              required: true
              description: Unique package Id
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

    file = request.files["executionPackage"]
    assert file.filename
    file_name = secure_filename(file.filename)

    with tempfile.TemporaryDirectory() as tmpdirname:
        file_path = os.path.join(tmpdirname, file_name)
        file.save(file_path)

        with open(file_path, "rb") as zip_file:
            b64_bytes = base64.b64encode(zip_file.read())
            b64_str = b64_bytes.decode()

    resp = call_rpc(rpc.UploadPackage.Request(id=get_id(), args=rpc.UploadPackage.Request.Args(packageId, b64_str)))

    if resp.result:
        return Response(status=200)
    else:
        return jsonify(resp.messages), 501


@app.route("/packages/<string:packageId>", methods=["GET"])
def get_package(packageId: str) -> RespT:  # noqa
    """Get execution package.
    ---
    get:
      summary: Get zip file with execution package.
      operationId: GetPackage
      tags:
        - Packages
      parameters:
        - in: path
          name: packageId
          schema:
            type: string
          required: true
          description: Unique package Id
      responses:
        200:
          description: Return archive of the execution package (.zip).
          content:
            application/zip:
              schema:
                type: string
                format: binary
        404:
          description: Package ID was not found.
          content:
            application/json:
              schema:
                type: string
    """

    if not package_exists(packageId):
        return jsonify("Not found"), 404

    with tempfile.TemporaryDirectory() as tmpdirname:

        archive_path = os.path.join(tmpdirname, packageId)
        shutil.make_archive(archive_path, "zip", os.path.join(PROJECT_PATH, packageId))

        return send_file(archive_path + ".zip", as_attachment=True, max_age=0)


@app.route("/packages", methods=["GET"])
def get_packages() -> RespT:
    """Gets summary for all stored execution packages.
    ---
    get:
      summary: Gets summary for all stored execution packages.
      operationId: GetSummaryPackages
      tags:
        - Packages
      responses:
        200:
          description: Summary of all packages on execution service.
          content:
            application/json:
              schema:
                type: array
                items:
                  $ref: SummaryPackage
    """

    resp = call_rpc(rpc.ListPackages.Request(id=get_id()))
    assert isinstance(resp, rpc.ListPackages.Response)

    ret: List[Dict] = []

    for pck in resp.data:
        sp = SummaryPackage(pck.id)
        sp.name = pck.package_meta.name
        sp.created = pck.package_meta.built
        sp.executed = pck.package_meta.executed
        if pck.project_meta:
            sp.project = SummaryProject(pck.project_meta.id, pck.project_meta.name, pck.project_meta.description)
        ret.append(sp.to_dict())

    return jsonify(ret), 200


@app.route("/packages/<string:packageId>", methods=["DELETE"])
def delete_package(packageId: str) -> RespT:  # noqa
    """Delete package.
    ---
    delete:
      summary: Delete package.
      operationId: DeletePackage
      tags:
        - Packages
      parameters:
        - in: path
          name: packageId
          description: Unique package Id
          schema:
            type: string
          required: true
          description: unique ID
      responses:
        200:
          description: Ok
        404:
          description: Package not found
          content:
            application/json:
              schema:
                type: string
        501:
          description: Contains array of errors.
          content:
            application/json:
              schema:
                type: array
                items:
                  type: string
    """

    if not package_exists(packageId):
        return jsonify("Not found"), 404

    resp = call_rpc(rpc.DeletePackage.Request(id=get_id(), args=arcor2_rpc.common.IdArgs(id=packageId)))

    if resp.result:
        return Response(status=200)
    else:
        return jsonify(resp.messages), 501


@app.route("/packages/<string:packageId>/start", methods=["PUT"])
def package_start(packageId: str) -> RespT:  # noqa
    """Run project
    ---
    put:
      summary: Start execution of the execution package.
      operationId: StartPackage
      tags:
        - Packages
      parameters:
        - in: path
          name: packageId
          schema:
            type: string
          required: true
          description: Unique package Id
      responses:
        200:
          description: Ok
        404:
          description: Package not found
          content:
            application/json:
              schema:
                type: string
        501:
            description: Contains array of errors.
            content:
              application/json:
                schema:
                  type: array
                  items:
                    type: string
    """

    if not package_exists(packageId):
        return jsonify("Not found"), 404

    resp = call_rpc(rpc.RunPackage.Request(id=get_id(), args=rpc.RunPackage.Request.Args(id=packageId)))

    if resp.result:
        return Response(status=200)
    else:
        return jsonify(resp.messages), 501


@app.route("/packages/stop", methods=["PUT"])
def packages_stop() -> RespT:
    """Stops running project
    ---
    put:
      summary: Stops execution of the given package.
      operationId: StopPackage
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

    resp = call_rpc(rpc.StopPackage.Request(id=get_id()))

    if resp.result:
        return Response(status=200)
    else:
        return jsonify(resp.messages), 501


@app.route("/packages/pause", methods=["PUT"])
def packages_pause() -> RespT:
    """Pauses running package.
    ---
    put:
      summary: Pause execution of the given package.
      operationId: PausePackage
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

    resp = call_rpc(rpc.PausePackage.Request(id=get_id()))

    if resp.result:
        return Response(status=200)
    else:
        return jsonify(resp.messages), 501


@app.route("/packages/resume", methods=["PUT"])
def packages_resume() -> RespT:
    """Resumes running package.
    ---
    put:
      summary: Resumes execution of the given package.
      operationId: ResumePackage
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

    resp = call_rpc(rpc.ResumePackage.Request(id=get_id()))

    if resp.result:
        return Response(status=200)
    else:
        return jsonify(resp.messages), 501


@app.route("/packages/executioninfo", methods=["GET"])
def packages_executioninfo() -> RespT:
    """/packages/executioninfo
    ---
    get:
      summary: /packages/executioninfo
      operationId: GetExecutionInfo
      tags:
        - Packages
      responses:
        200:
          description: Execution information
          content:
            application/json:
              schema:
                $ref: ExecutionInfo
        501:
          description: Internal error
          content:
            application/json:
              schema:
                type: string
    """

    if package_state is None or package_state.state == PackageState.Data.StateEnum.UNDEFINED:
        ret = ExecutionInfo(ExecutionState.Undefined)
    elif package_state.state == PackageState.Data.StateEnum.RUNNING:
        ret = ExecutionInfo(ExecutionState.Running, package_state.package_id)
    elif package_state.state == PackageState.Data.StateEnum.PAUSED:
        ret = ExecutionInfo(ExecutionState.Paused, package_state.package_id)
    elif package_state.state in (PackageState.Data.StateEnum.PAUSING, PackageState.Data.StateEnum.STOPPING):
        ret = ExecutionInfo(ExecutionState.Pending, package_state.package_id)
    elif package_state.state == PackageState.Data.StateEnum.STOPPED:

        if exception_messages:
            ret = ExecutionInfo(ExecutionState.Faulted, package_state.package_id, " ".join(exception_messages))
        else:
            ret = ExecutionInfo(ExecutionState.Completed, package_state.package_id)
    else:
        return jsonify("Unhandled state"), 501

    return jsonify(ret.to_dict()), 200


def main() -> None:

    parser = argparse.ArgumentParser(description=SERVICE_NAME)
    parser.add_argument("-s", "--swagger", action="store_true", default=False)
    args = parser.parse_args()

    global ws

    while not args.swagger:
        try:
            ws = websocket.create_connection(EXE_URL, enable_multithread=True)
            thread = Thread(target=ws_thread, daemon=True)
            thread.start()
            break
        except ConnectionRefusedError:
            print("Connecting to the Execution service...")
            time.sleep(1.0)

    run_app(
        app,
        SERVICE_NAME,
        arcor2_execution_rest_proxy.version(),
        "0.7.0",
        PORT,
        [SummaryPackage, ExecutionInfo, Token],
        args.swagger,
    )


if __name__ == "__main__":
    main()
