#!/usr/bin/env python3

import argparse
import json
import os
from functools import wraps
from typing import Dict, Optional, Tuple, Type

from apispec import APISpec
from apispec_webframeworks.flask import FlaskPlugin
from arcor2_dobot import version
from arcor2_dobot.dobot import Dobot, MoveType
from arcor2_dobot.m1 import DobotM1
from arcor2_dobot.magician import DobotMagician
from dataclasses_jsonschema.apispec import DataclassesPlugin
from flask import Flask, jsonify, request
from flask_cors import CORS
from flask_swagger_ui import get_swaggerui_blueprint

from arcor2.data.common import Joint, Pose
from arcor2.exceptions import Arcor2Exception
from arcor2.helpers import port_from_url
from arcor2.logging import get_logger

logger = get_logger(__name__)

URL = os.getenv("ARCOR2_DOBOT_URL", "http://localhost:5018")
SERVICE_NAME = "Dobot Service"

# Create an APISpec
spec = APISpec(
    title=SERVICE_NAME,
    version=version(),
    openapi_version="3.0.2",
    plugins=[FlaskPlugin(), DataclassesPlugin()],
)

app = Flask(__name__)
CORS(app)

_dobot: Optional[Dobot] = None
_mock = False


@app.route("/swagger/api/swagger.json", methods=["GET"])
def get_swagger() -> str:
    return json.dumps(spec.to_dict())


def started() -> bool:

    return _dobot is not None


def requires_started(f):
    @wraps(f)
    def wrapped(*args, **kwargs):
        if not started():
            return "Not started", 403
        return f(*args, **kwargs)

    return wrapped


@app.route("/start", methods=["PUT"])
def put_start() -> Tuple[str, int]:
    """Start the robot.
    ---
    put:
        description: Start the robot.
        tags:
           - State
        parameters:
            - in: query
              name: port
              schema:
                type: string
                default: /dev/dobot
              description: Dobot port
            - in: query
              name: model
              schema:
                type: string
                enum:
                    - magician
                    - m1
              required: true
              description: Dobot Model
        requestBody:
              content:
                application/json:
                  schema:
                    $ref: Pose
        responses:
            200:
              description: Ok
            403:
              description: Already started
    """

    if started():
        return "Already started.", 403

    model: str = request.args.get("model", default="magician")
    port: str = request.args.get("port", default="/dev/dobot")
    pose = Pose.from_dict(request.json)

    mapping: Dict[str, Type[Dobot]] = {"magician": DobotMagician, "m1": DobotM1}

    global _dobot

    _dobot = mapping[model](pose, port, _mock)

    return "ok", 200


@app.route("/stop", methods=["PUT"])
@requires_started
def put_stop() -> Tuple[str, int]:
    """Stop the robot.
    ---
    put:
        description: Stop the robot.
        tags:
           - State
        responses:
            200:
              description: Ok
            403:
              description: Not started
    """

    global _dobot
    assert _dobot is not None
    _dobot.cleanup()
    _dobot = None
    return "ok", 200


@app.route("/started", methods=["GET"])
def get_started() -> Tuple[str, int]:
    """Get the current state.
    ---
    get:
        description: Get the current state.
        tags:
           - State
        responses:
            200:
              description: Ok
              content:
                application/json:
                    schema:
                        type: boolean
            403:
              description: Not started
    """

    return jsonify(started()), 200


@app.route("/eef/pose", methods=["GET"])
@requires_started
def get_eef_pose() -> Tuple[str, int]:
    """Get the EEF pose.
    ---
    get:
        description: Get the EEF pose.
        tags:
           - Robot
        responses:
            200:
              description: Ok
              content:
                application/json:
                    schema:
                        $ref: Pose
            403:
              description: Not started
    """

    assert _dobot is not None
    return jsonify(_dobot.get_end_effector_pose()), 200


@app.route("/eef/pose", methods=["PUT"])
@requires_started
def put_eef_pose() -> Tuple[str, int]:
    """Set the EEF pose.
    ---
    put:
        description: Set the EEF pose.
        tags:
           - Robot
        parameters:
            - in: query
              name: moveType
              schema:
                type: string
                enum:
                    - JUMP
                    - LINEAR
                    - JOINTS
              required: true
              description: Move type
            - name: velocity
              in: query
              schema:
                type: number
                format: float
                minimum: 0
                maximum: 100
            - name: acceleration
              in: query
              schema:
                type: number
                format: float
                minimum: 0
                maximum: 100
        requestBody:
              content:
                application/json:
                  schema:
                    $ref: Pose
        responses:
            200:
              description: Ok
              content:
                application/json:
                    schema:
                        $ref: Pose
            403:
              description: Not started
    """

    assert _dobot is not None
    pose = Pose.from_dict(request.json)
    move_type: str = request.args.get("moveType", "jump")
    velocity = float(request.args.get("velocity", default=50.0))
    acceleration = float(request.args.get("acceleration", default=50.0))

    _dobot.move(pose, MoveType(move_type), velocity, acceleration)
    return "ok", 200


@app.route("/home", methods=["PUT"])
@requires_started
def put_home() -> Tuple[str, int]:
    """Get the current state.
    ---
    put:
        description: Get the current state.
        tags:
           - Robot
        responses:
            200:
              description: Ok
            403:
              description: Not started
    """

    assert _dobot is not None
    _dobot.home()
    return "ok", 200


@app.route("/suck", methods=["PUT"])
@requires_started
def put_suck() -> Tuple[str, int]:
    """Get the current state.
    ---
    put:
        description: Get the current state.
        tags:
           - Robot
        responses:
            200:
              description: Ok
            403:
              description: Not started
    """

    assert _dobot is not None
    _dobot.suck()
    return "ok", 200


@app.route("/release", methods=["PUT"])
@requires_started
def put_release() -> Tuple[str, int]:
    """Get the current state.
    ---
    put:
        description: Get the current state.
        tags:
           - Robot
        responses:
            200:
              description: Ok
            403:
              description: Not started
    """

    assert _dobot is not None
    _dobot.release()
    return "ok", 200


@app.route("/joints", methods=["GET"])
@requires_started
def get_joints() -> Tuple[str, int]:
    """Get the current state.
    ---
    get:
        description: Get the current state.
        tags:
           - Robot
        responses:
            200:
              description: Ok
              content:
                application/json:
                    schema:
                        type: array
                        items:
                            $ref: Joint
            403:
              description: Not started
    """

    assert _dobot is not None
    return jsonify(_dobot.robot_joints()), 200


@app.route("/ik", methods=["PUT"])
@requires_started
def put_ik() -> Tuple[str, int]:
    """Get the current state.
    ---
    put:
        description: Get the current state.
        tags:
           - Robot
        requestBody:
              content:
                application/json:
                  schema:
                    $ref: Pose
        responses:
            200:
              description: Ok
              content:
                application/json:
                    schema:
                        type: array
                        items:
                            $ref: Joint
            403:
              description: Not started
    """

    assert _dobot is not None

    pose = Pose.from_dict(request.json)
    return jsonify(_dobot.inverse_kinematics(pose)), 200


@app.route("/fk", methods=["PUT"])
@requires_started
def put_fk() -> Tuple[str, int]:
    """Get the current state.
    ---
    put:
        description: Get the current state.
        tags:
           - Robot
        requestBody:
              content:
                application/json:
                  schema:
                    type: array
                    items:
                        $ref: Joint
        responses:
            200:
              description: Ok
              content:
                application/json:
                    schema:
                        $ref: Pose
            403:
              description: Not started
    """

    assert _dobot is not None

    joints = [Joint.from_dict(j) for j in request.json]
    return jsonify(_dobot.forward_kinematics(joints)), 200


@app.errorhandler(Arcor2Exception)
def handle_bad_request(e: Arcor2Exception) -> Tuple[str, int]:
    return str(e), 400


with app.test_request_context():
    spec.path(view=put_start)
    spec.path(view=put_stop)
    spec.path(view=get_started)
    spec.path(view=get_eef_pose)
    spec.path(view=put_eef_pose)
    spec.path(view=put_home)
    spec.path(view=put_suck)
    spec.path(view=put_release)
    spec.path(view=get_joints)
    spec.path(view=put_ik)
    spec.path(view=put_fk)

spec.components.schema(Pose.__name__, schema=Pose)
spec.components.schema(Joint.__name__, schema=Joint)


def main() -> None:

    parser = argparse.ArgumentParser(description=SERVICE_NAME)
    parser.add_argument("-s", "--swagger", action="store_true", default=False)
    parser.add_argument("-m", "--mock", action="store_true", default=False)
    args = parser.parse_args()

    if args.swagger:
        print(spec.to_yaml())
        return

    global _mock
    _mock = args.mock
    if _mock:
        logger.info("Starting as a mock!")

    SWAGGER_URL = "/swagger"

    swaggerui_blueprint = get_swaggerui_blueprint(
        SWAGGER_URL, "./api/swagger.json"  # Swagger UI static files will be mapped to '{SWAGGER_URL}/dist/'
    )

    # Register blueprint at URL
    app.register_blueprint(swaggerui_blueprint, url_prefix=SWAGGER_URL)

    app.run(host="0.0.0.0", port=port_from_url(URL))

    if _dobot:
        _dobot.cleanup()


if __name__ == "__main__":
    main()
