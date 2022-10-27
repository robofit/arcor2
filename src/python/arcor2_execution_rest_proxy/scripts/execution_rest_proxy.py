#!/usr/bin/env python3

import argparse
import base64
import os
import shutil
import tempfile
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from queue import Queue
from threading import Thread
from typing import TYPE_CHECKING, Optional

import fastuuid as uuid
import websocket
from dataclasses_jsonschema import DEFAULT_SCHEMA_TYPE, FieldMeta, JsonSchemaMixin
from flask import Response, jsonify, request, send_file
from sqlitedict import SqliteDict
from werkzeug.utils import secure_filename

import arcor2_execution_rest_proxy
from arcor2 import json
from arcor2.data import events
from arcor2.data import rpc as arcor2_rpc
from arcor2.data.events import ActionStateAfter, ActionStateBefore, PackageInfo, PackageState, ProjectException
from arcor2.data.rpc import get_id
from arcor2.flask import RespT, create_app, run_app
from arcor2_execution_data import EVENTS, EXPOSED_RPCS
from arcor2_execution_data import URL as EXE_URL
from arcor2_execution_data import rpc
from arcor2_execution_rest_proxy.exceptions import NotFound, PackageRunState, RpcFail, WebApiError
from arcor2_runtime.package import PROJECT_PATH

PORT = int(os.getenv("ARCOR2_EXECUTION_PROXY_PORT", 5009))
SERVICE_NAME = "Execution Web API"
DEPENDENCIES: None | dict[str, str] = None

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

    id: str = field(
        metadata=FieldMeta(
            schema_type=DEFAULT_SCHEMA_TYPE,
            description="Project id.",
        ).as_dict
    )
    name: str = field(
        metadata=FieldMeta(
            schema_type=DEFAULT_SCHEMA_TYPE,
            description="Project name.",
        ).as_dict
    )
    description: str = field(
        metadata=FieldMeta(
            schema_type=DEFAULT_SCHEMA_TYPE,
            description="Project description.",
        ).as_dict
    )


@dataclass
class SummaryPackage(JsonSchemaMixin):
    """Describes execution package."""

    id: str = field(
        metadata=FieldMeta(
            schema_type=DEFAULT_SCHEMA_TYPE,
            description="Execution package id.",
        ).as_dict
    )
    name: Optional[str] = field(
        default=None, metadata=FieldMeta(schema_type=DEFAULT_SCHEMA_TYPE, description="Execution package name.").as_dict
    )
    created: Optional[datetime] = field(
        default=None, metadata=FieldMeta(schema_type=DEFAULT_SCHEMA_TYPE, description="Date of creation.").as_dict
    )
    executed: Optional[datetime] = field(
        default=None, metadata=FieldMeta(schema_type=DEFAULT_SCHEMA_TYPE, description="Date of last execution.").as_dict
    )
    project: Optional[SummaryProject] = field(
        default=None,
        metadata=FieldMeta(schema_type=DEFAULT_SCHEMA_TYPE, description="Related project description.").as_dict,
    )


@dataclass
class ExecutionInfo(JsonSchemaMixin):
    """Stores information about package execution."""

    state: ExecutionState = field(
        metadata=FieldMeta(
            schema_type=DEFAULT_SCHEMA_TYPE,
            description="Execution process state descriptor.",
        ).as_dict
    )
    activePackageId: Optional[str] = field(
        default=None,
        metadata=FieldMeta(schema_type=DEFAULT_SCHEMA_TYPE, description="Id of the active execution package.").as_dict,
    )
    exceptionMessage: Optional[str] = field(
        default=None,
        metadata=FieldMeta(
            schema_type=DEFAULT_SCHEMA_TYPE, description="Message of occurred exception if any."
        ).as_dict,
    )
    actionPointIds: Optional[set[str]] = field(
        default=None,
        metadata=FieldMeta(
            schema_type=DEFAULT_SCHEMA_TYPE,
            description="List of action points ids relevant to the current execution point.",
        ).as_dict,
    )


@dataclass
class Token(JsonSchemaMixin):
    """Describes Token."""

    id: str = field(
        metadata=FieldMeta(
            schema_type=DEFAULT_SCHEMA_TYPE,
            description="Token id.",
        ).as_dict
    )
    name: str = field(
        metadata=FieldMeta(
            schema_type=DEFAULT_SCHEMA_TYPE,
            description="Token name.",
        ).as_dict
    )
    access: Optional[bool] = field(
        default=False,
        metadata=FieldMeta(
            schema_type=DEFAULT_SCHEMA_TYPE,
            description="Token access permission.",
        ).as_dict,
    )


app = create_app(__name__)

ws: None | websocket.WebSocket = None

if TYPE_CHECKING:
    ReqQueue = Queue[arcor2_rpc.common.RPC.Request]  # this is only processed by mypy
    RespQueue = Queue[arcor2_rpc.common.RPC.Response]
else:
    ReqQueue = Queue  # this is not seen by mypy but will be executed at runtime.
    RespQueue = Queue


rpc_request_queue: ReqQueue = ReqQueue()
rpc_responses: dict[int, RespQueue] = {}

package_state: PackageState.Data = PackageState.Data()
package_info: None | PackageInfo.Data = None
exception_messages: list[str] = []

# hold last action state for AP visualization
# do not unset ActionStateBefore event, this information might be used even after ActionStateAfter event
action_state_before: None | ActionStateBefore.Data = None
action_state_after: None | ActionStateAfter.Data = None

breakpoints: dict[str, set[str]] = {}


@contextmanager
def tokens_db():
    """This is a wrapper for SqliteDict enabling one to change all settings at
    one place."""

    with SqliteDict(TOKENS_DB_PATH, autocommit=True, encode=json.dumps, decode=json.loads) as tokens:
        yield tokens


def ws_thread() -> None:  # TODO use (refactored) arserver client

    global package_info
    global package_state
    global action_state_before
    global action_state_after
    assert ws

    event_mapping: dict[str, type[events.Event]] = {evt.__name__: evt for evt in EVENTS}
    rpc_mapping: dict[str, type[arcor2_rpc.common.RPC]] = {rpc.__name__: rpc for rpc in EXPOSED_RPCS}

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
            elif isinstance(evt, ActionStateBefore):
                # assume ActionStateBefore event to be fired always before ActionStateAfter
                # thus ActionStateBefore here belong to previous action - unset it
                action_state_after = None
                action_state_before = evt.data
            elif isinstance(evt, ActionStateAfter):
                action_state_after = evt.data

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


def package_run_state() -> bool:
    """The script is up."""
    return package_state.state in PackageState.RUN_STATES


def package_running() -> bool:
    return package_state.state == PackageState.Data.StateEnum.RUNNING


def package_paused() -> bool:
    return package_state.state == PackageState.Data.StateEnum.PAUSED


def package_stopped() -> bool:
    """The script is down."""
    return package_state.state in PackageState.RUNNABLE_STATES


@app.route("/tokens/create", methods=["POST"])
def post_token() -> RespT:
    """Create new token
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
            500:
              description: "Error types: **General**."
              content:
                application/json:
                  schema:
                    $ref: WebApiError
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
      summary: Lists all existing tokens.
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
        500:
          description: "Error types: **General**."
          content:
            application/json:
              schema:
                $ref: WebApiError
    """

    with tokens_db() as tokens:
        return jsonify(list(tokens.values())), 200


@app.route("/tokens/<string:id>", methods=["DELETE"])
def delete_token(id: str) -> RespT:  # noqa
    """Delete token.
    ---
    delete:
      summary: Deletes a given token from known tokens.
      operationId: RemoveToken
      tags:
        - Tokens
      parameters:
        - in: path
          name: id
          schema:
            type: string
          required: true
          description: unique token ID
      responses:
        200:
          description: Token has been deleted
        500:
          description: "Error types: **General**, **NotFound**."
          content:
            application/json:
              schema:
                $ref: WebApiError
    """

    with tokens_db() as tokens:
        try:
            del tokens[id]
        except KeyError:
            raise NotFound("Token not found")

    return Response(status=200)


@app.route("/tokens/<string:id>/access", methods=["PUT"])
def put_token_access(id: str) -> RespT:  # noqa
    """Set token access rights
    ---
    put:
        summary: Sets execution access rights for given token.
        operationId: SetAccess
        tags:
           - Tokens
        parameters:
            - in: path
              name: id
              schema:
                type: string
              required: true
              description: Token id to have access value changed.
            - in: query
              name: access
              schema:
                type: boolean
              required: true
              description: New token access value.
        responses:
            200:
              description: Access rights has been successfully changed
            500:
              description: "Error types: **General**, **NotFound**."
              content:
                application/json:
                  schema:
                    $ref: WebApiError
    """

    with tokens_db() as tokens:
        try:
            token = Token.from_dict(tokens[id])
        except KeyError:
            raise NotFound("Token not found.")
        token.access = request.args["access"] == "true"
        tokens[id] = token.to_dict()

    return Response(status=200)


@app.route("/tokens/<string:id>/access", methods=["GET"])
def get_token_access(id: str) -> RespT:  # noqa
    """Gets execution access rights for given token
    ---
    get:
        summary: Gets execution access rights for given token.
        operationId: GetAccess
        tags:
           - Tokens
        parameters:
            - in: path
              name: id
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
            500:
              description: "Error types: **General**, **NotFound**."
              content:
                application/json:
                  schema:
                    $ref: WebApiError
    """

    with tokens_db() as tokens:
        try:
            token = Token.from_dict(tokens[id])
        except KeyError:
            raise NotFound("Token not found.")
        return jsonify(token.access), 200


@app.route("/packages/<string:id>", methods=["POST"])
def post_package(id: str) -> RespT:  # noqa
    """Create execution package with supplied id
    ---
    post:
        summary: Adds the execution package.
        operationId: PostPackage
        tags:
           - Packages
        parameters:
            - in: path
              name: id
              schema:
                type: string
              required: true
              description: Unique execution package Id
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
              description: The execution package has been successfully created
            500:
              description: "Error types: **General**, **RpcFail**."
              content:
                application/json:
                  schema:
                    $ref: WebApiError
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

    resp = call_rpc(rpc.UploadPackage.Request(id=get_id(), args=rpc.UploadPackage.Request.Args(id, b64_str)))

    if resp.result:
        return Response(status=200)

    raise RpcFail("Failed to post the execution package.", content=json.dumps(resp.messages))


@app.route("/packages/<string:id>", methods=["GET"])
def get_package(id: str) -> RespT:  # noqa
    """Get execution package.
    ---
    get:
      summary: Gets a zip file with the execution package.
      operationId: GetPackage
      tags:
        - Packages
      parameters:
        - in: path
          name: id
          schema:
            type: string
          required: true
          description: Unique execution package Id
      responses:
        200:
          description: Return archive of the execution package (.zip).
          content:
            application/zip:
              schema:
                type: string
                format: binary
        500:
          description: "Error types: **General**, **NotFound**."
          content:
            application/json:
              schema:
                $ref: WebApiError
    """

    if not package_exists(id):
        raise NotFound("Execution package ID not found.")

    with tempfile.TemporaryDirectory() as tmpdirname:
        archive_path = os.path.join(tmpdirname, id)
        shutil.make_archive(archive_path, "zip", os.path.join(PROJECT_PATH, id))

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
          description: Summary of all execution packages on service.
          content:
            application/json:
              schema:
                type: array
                items:
                  $ref: SummaryPackage
        500:
          description: "Error types: **General**"
          content:
            application/json:
              schema:
                $ref: WebApiError
    """

    resp = call_rpc(rpc.ListPackages.Request(id=get_id()))
    assert isinstance(resp, rpc.ListPackages.Response)

    ret: list[dict] = []

    for pck in resp.data:
        sp = SummaryPackage(pck.id)
        sp.name = pck.package_meta.name
        sp.created = pck.package_meta.built
        sp.executed = pck.package_meta.executed
        if pck.project_meta:
            sp.project = SummaryProject(pck.project_meta.id, pck.project_meta.name, pck.project_meta.description)
        ret.append(sp.to_dict())

    return jsonify(ret), 200


@app.route("/packages/<string:id>", methods=["DELETE"])
def delete_package(id: str) -> RespT:  # noqa
    """Delete the execution package.
    ---
    delete:
      summary: Deletes the execution package.
      operationId: DeletePackage
      tags:
        - Packages
      parameters:
        - in: path
          name: id
          description: Unique execution package Id
          schema:
            type: string
          required: true
          description: unique ID
      responses:
        200:
          description: Ok
        500:
          description: "Error types: **General**, **NotFound**, **RpcFail**."
          content:
            application/json:
              schema:
                $ref: WebApiError
    """

    if not package_exists(id):
        raise NotFound("Execution package ID not found.")

    resp = call_rpc(rpc.DeletePackage.Request(id=get_id(), args=arcor2_rpc.common.IdArgs(id=id)))

    if resp.result:
        breakpoints.pop(id, None)
        return Response(status=200)

    raise RpcFail("Failed to delete the execution package.", content=json.dumps(resp.messages))


@app.route("/packages/<string:id>/start", methods=["PUT"])
def package_start(id: str) -> RespT:  # noqa
    """Run project
    ---
    put:
      summary: Starts execution of the execution package.
      operationId: StartPackage
      tags:
        - Packages
      parameters:
        - in: path
          name: id
          schema:
            type: string
          required: true
          description: Unique execution package Id
      responses:
        200:
          description: Execution was successfully started.
        500:
          description:
            "Error types: **General**, **NotFound**, **PackageRunState**, **RpcFail**."
          content:
            application/json:
              schema:
                $ref: WebApiError
    """

    if not package_exists(id):
        raise NotFound("Execution package ID not found.")

    if package_run_state():
        raise PackageRunState("Another execution package is running or paused.")

    resp = call_rpc(rpc.RunPackage.Request(id=get_id(), args=rpc.RunPackage.Request.Args(id=id)))

    if resp.result:
        breakpoints.pop(id, None)
        return Response(status=200)

    raise RpcFail("Failed to start the execution package.", content=json.dumps(resp.messages))


@app.route("/packages/<string:id>/breakpoints", methods=["PUT"])
def put_breakpoints(id: str) -> RespT:  # noqa
    """Add breakpoints for the execution package
    ---
    put:
      summary: Adds breakpoints for the execution package.
      operationId: UpdateBreakpoints
      tags:
        - Packages
      parameters:
        - in: path
          name: id
          schema:
            type: string
          required: true
          description: The unique identification of the execution package.
        - in: query
          name: breakpoints
          schema:
            type: array
            items:
              type: string
          required: true
          description: List of breakpoints (IDs of action points).
      responses:
        200:
          description: Breakpoints were updated.
        500:
          description:
            "Error types: **General**, **NotFound**, **PackageRunState**."
          content:
            application/json:
              schema:
                $ref: WebApiError
    """

    if not package_exists(id):
        raise NotFound("Execution package ID not found.")

    if not package_stopped():
        raise PackageRunState("Can't put breakpoints when the execution package is active (running or paused).")

    breakpoints[id] = set(request.args.getlist("breakpoints"))
    return Response(status=200)


@app.route("/packages/<string:id>/breakpoints", methods=["GET"])
def get_breakpoints(id: str) -> RespT:  # noqa
    """Get breakpoints for the execution package
    ---
    get:
      summary: Gets breakpoints for the execution package.
      operationId: GetBreakpoints
      tags:
        - Packages
      parameters:
        - in: path
          name: id
          schema:
            type: string
          required: true
          description: The unique identification of the execution package.
      responses:
        200:
            description: List of breakpoints for the execution package.
            content:
              application/json:
                schema:
                  type: array
                  items:
                    type: string
        500:
          description: "Error types: **General**, **NotFound**."
          content:
            application/json:
              schema:
                $ref: WebApiError
    """

    if not package_exists(id):
        raise NotFound("Execution package ID not found.")

    return jsonify(list(breakpoints.get(id, [])))


@app.route("/packages/<string:id>/debug", methods=["PUT"])
def package_debug(id: str) -> RespT:  # noqa
    """Debug project
    ---
    put:
      summary: Starts debugging of the execution package.
      operationId: DebugPackage
      tags:
        - Packages
      parameters:
        - in: path
          name: id
          schema:
            type: string
          required: true
          description: The unique identification of the execution package.
        - in: query
          name: breakOnFirstAction
          schema:
            type: boolean
            default: false
          description: The project execution is paused before the first Action (default value is false).
      responses:
        200:
          description: The debugging process successfully started.
        500:
          description: "Error types: **General**, **NotFound**, **RpcFail**."
          content:
            application/json:
              schema:
                $ref: WebApiError
    """

    if not package_exists(id):
        raise NotFound("Execution package ID not found.")

    if package_run_state():
        raise PackageRunState("Another execution package is active (running or paused).")

    resp = call_rpc(
        rpc.RunPackage.Request(
            id=get_id(),
            args=rpc.RunPackage.Request.Args(
                id,
                request.args.get("breakOnFirstAction", default="false") == "true",
                breakpoints.get(id, None),
            ),
        )
    )

    if resp.result:
        return Response(status=200)

    raise RpcFail("Failed to debug the execution package.", content=json.dumps(resp.messages))


@app.route("/packages/stop", methods=["PUT"])
def packages_stop() -> RespT:
    """Stops running the execution package.
    ---
    put:
      summary: Stops execution of the active execution package.
      operationId: StopPackage
      tags:
        - Packages
      responses:
        200:
          description: The execution package has been successfully stopped.
        500:
          description: "Error types: **General**, **PackageRunState**, **RpcFail**."
          content:
            application/json:
              schema:
                $ref: WebApiError
    """

    if not package_run_state():
        raise PackageRunState("The execution package is not running.")

    resp = call_rpc(rpc.StopPackage.Request(id=get_id()))

    if resp.result:
        return Response(status=200)

    raise RpcFail("Failed to stop the execution package.", content=json.dumps(resp.messages))


@app.route("/packages/step", methods=["PUT"])
def packages_step() -> RespT:
    """Step to the next action.
    ---
    put:
      summary: Step to the next action.
      operationId: StepPackage
      tags:
        - Packages
      responses:
        200:
          description: Step was successfully performed.
        500:
          description: "Error types: **General**, **PackageRunState**, **RpcFail**."
          content:
            application/json:
              schema:
                $ref: WebApiError
    """

    if not package_paused():
        raise PackageRunState("The execution package is not paused.")

    resp = call_rpc(rpc.StepAction.Request(id=get_id()))

    if resp.result:
        return Response(status=200)

    raise RpcFail("Failed to stop the execution package.", content=json.dumps(resp.messages))


@app.route("/packages/pause", methods=["PUT"])
def packages_pause() -> RespT:
    """Pauses running the execution package.
    ---
    put:
      summary: Pauses execution of the active execution package.
      operationId: PausePackage
      tags:
        - Packages
      responses:
        200:
          description: The execution package has been successfully paused.
        500:
          description: "Error types: **General**, **PackageRunState**, **RpcFail**."
          content:
            application/json:
              schema:
                $ref: WebApiError
    """

    if not package_running():
        raise PackageRunState("The execution package is not running.")

    resp = call_rpc(rpc.PausePackage.Request(id=get_id()))

    if resp.result:
        return Response(status=200)

    raise RpcFail("Failed to pause the execution package.", content=json.dumps(resp.messages))


@app.route("/packages/resume", methods=["PUT"])
def packages_resume() -> RespT:
    """Resumes running of the execution package.
    ---
    put:
      summary: Resumes running of the active execution package.
      operationId: ResumePackage
      tags:
        - Packages
      responses:
        200:
          description: The execution package has been successfully resumed.
        500:
          description: "Error types: **General**, **PackageRunState**, **RpcFail**."
          content:
            application/json:
              schema:
                $ref: WebApiError
    """

    if not package_paused():
        raise PackageRunState("The execution package is not paused.")

    resp = call_rpc(rpc.ResumePackage.Request(id=get_id()))

    if resp.result:
        return Response(status=200)

    raise RpcFail("Failed to resume the execution package.", content=json.dumps(resp.messages))


@app.route("/packages/state", methods=["GET"])
def packages_state() -> RespT:
    """Get information about current execution state.
    ---
    get:
      summary: Gets information about current execution state.
      operationId: PackagesState
      tags:
        - Packages
      responses:
        200:
          description: Execution information
          content:
            application/json:
              schema:
                $ref: ExecutionInfo
        500:
          description: "Error types: **General**"
          content:
            application/json:
              schema:
                $ref: WebApiError
    """

    if package_state.state == PackageState.Data.StateEnum.UNDEFINED:
        ret = ExecutionInfo(ExecutionState.Undefined)
    elif package_state.state == PackageState.Data.StateEnum.RUNNING:
        ret = ExecutionInfo(ExecutionState.Running, package_state.package_id)
    elif package_state.state == PackageState.Data.StateEnum.PAUSED:
        ret = ExecutionInfo(ExecutionState.Paused, package_state.package_id)
    elif package_state.state in (
        PackageState.Data.StateEnum.PAUSING,
        PackageState.Data.StateEnum.STOPPING,
        PackageState.Data.StateEnum.RESUMING,
    ):
        ret = ExecutionInfo(ExecutionState.Pending, package_state.package_id)
    elif package_state.state == PackageState.Data.StateEnum.STOPPED:

        if exception_messages:
            ret = ExecutionInfo(ExecutionState.Faulted, package_state.package_id, " ".join(exception_messages))
        else:
            ret = ExecutionInfo(ExecutionState.Completed, package_state.package_id)
    else:
        ret = ExecutionInfo(ExecutionState.Undefined)  # TODO this is unhandled state - log it

    if action_state_before is not None:
        ret.actionPointIds = action_state_before.action_point_ids

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
        PORT,
        [SummaryPackage, ExecutionInfo, Token, WebApiError],
        args.swagger,
        dependencies=DEPENDENCIES,
    )


if __name__ == "__main__":
    main()
