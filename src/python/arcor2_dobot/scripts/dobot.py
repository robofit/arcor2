#!/usr/bin/env python3

import argparse
import os
from functools import wraps
from typing import Dict, Optional, Type

from arcor2_dobot import version
from arcor2_dobot.dobot import Dobot, MoveType
from arcor2_dobot.m1 import DobotM1
from arcor2_dobot.magician import DobotMagician
from flask import jsonify, request

from arcor2.data.common import Joint, Pose
from arcor2.flask import RespT, create_app, run_app
from arcor2.helpers import port_from_url
from arcor2.logging import get_logger

logger = get_logger(__name__)

URL = os.getenv("ARCOR2_DOBOT_URL", "http://localhost:5018")
SERVICE_NAME = "Dobot Service"

app = create_app(__name__)

_dobot: Optional[Dobot] = None
_mock = False


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
def put_start() -> RespT:
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
              description: Dobot model
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
def put_stop() -> RespT:
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
def get_started() -> RespT:
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
def get_eef_pose() -> RespT:
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
def put_eef_pose() -> RespT:
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
def put_home() -> RespT:
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
def put_suck() -> RespT:
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
def put_release() -> RespT:
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
def get_joints() -> RespT:
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
def put_ik() -> RespT:
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
def put_fk() -> RespT:
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


def main() -> None:

    parser = argparse.ArgumentParser(description=SERVICE_NAME)
    parser.add_argument("-s", "--swagger", action="store_true", default=False)
    parser.add_argument("-m", "--mock", action="store_true", default=False)
    args = parser.parse_args()

    global _mock
    _mock = args.mock
    if _mock:
        logger.info("Starting as a mock!")

    run_app(app, SERVICE_NAME, version(), version(), port_from_url(URL), [Pose, Joint], args.swagger)

    if _dobot:
        _dobot.cleanup()


if __name__ == "__main__":
    main()
