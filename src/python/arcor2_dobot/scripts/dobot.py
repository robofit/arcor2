#!/usr/bin/env python3

import argparse
import copy
import logging
import os
from functools import wraps
from typing import Optional

from arcor2_dobot import version
from arcor2_dobot.dobot import Dobot, DobotApiException, MoveType
from arcor2_dobot.m1 import DobotM1
from arcor2_dobot.magician import DobotMagician
from flask import Response, jsonify, request

from arcor2 import env, json
from arcor2.clients import scene_service
from arcor2.data.common import Joint, Pose
from arcor2.data.scene import LineCheck
from arcor2.flask import FlaskException, RespT, create_app, run_app
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


@app.route("/state/start", methods=["PUT"])
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
            204:
              description: Ok
            403:
              description: Already started
    """

    if started():
        return "Already started.", 403

    model: str = request.args.get("model", default="magician")
    port: str = request.args.get("port", default="/dev/dobot")

    if not isinstance(request.json, dict):
        raise FlaskException("Body should be a JSON dict containing Pose.", error_code=400)

    pose = Pose.from_dict(request.json)

    mapping: dict[str, type[Dobot]] = {"magician": DobotMagician, "m1": DobotM1}

    global _dobot

    _dobot = mapping[model](pose, port, _mock)

    return Response(status=204)


@app.route("/state/stop", methods=["PUT"])
@requires_started
def put_stop() -> RespT:
    """Stop the robot.
    ---
    put:
        description: Stop the robot.
        tags:
           - State
        responses:
            204:
              description: Ok
            403:
              description: Not started
    """

    global _dobot
    assert _dobot is not None
    _dobot.cleanup()
    _dobot = None
    return Response(status=204)


@app.route("/state/started", methods=["GET"])
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

    return jsonify(started())


@app.route("/conveyor/speed", methods=["PUT"])
@requires_started
def put_conveyor_speed() -> RespT:
    """Set the conveyor belt speed.
    ---
    put:
        description: Set the conveyor belt speed.
        tags:
           - Conveyor Belt
        parameters:
            - name: velocity
              in: query
              schema:
                type: number
                default: 50.0
                format: float
                minimum: 0
                maximum: 100
            - in: query
              name: direction
              schema:
                type: string
                default: forward
                enum:
                    - forward
                    - backwards
              description: Direction
        responses:
            204:
              description: Ok
            403:
              description: Not started
    """

    speed = float(request.args.get("velocity", default=50.0))
    direction = request.args.get("direction", default="forward")

    assert _dobot is not None
    _dobot.conveyor_speed(speed, 1 if direction == "forward" else -1)
    return Response(status=204)


@app.route("/conveyor/distance", methods=["PUT"])
@requires_started
def put_conveyor_distance() -> RespT:
    """Set the conveyor belt distance.
    ---
    put:
        description: Set the conveyor belt distance.
        tags:
           - Conveyor Belt
        parameters:
            - name: velocity
              in: query
              schema:
                type: number
                default: 50.0
                format: float
                minimum: 0
                maximum: 100
            - name: distance
              in: query
              schema:
                type: number
                default: 0.1
                format: float
                minimum: 0
            - in: query
              name: direction
              schema:
                type: string
                default: forward
                enum:
                    - forward
                    - backwards
              description: Direction
        responses:
            204:
              description: Ok
            403:
              description: Not started
    """

    speed = float(request.args.get("velocity", default=50.0))
    direction = request.args.get("direction", default="forward")
    distance = float(request.args.get("distance", default=0.1))

    assert _dobot is not None
    _dobot.conveyor_distance(speed, distance * 1000, 1 if direction == "forward" else -1)
    return Response(status=204)


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
            - in: query
              name: safe
              schema:
                type: boolean
                default: false
        requestBody:
              content:
                application/json:
                  schema:
                    $ref: Pose
        responses:
            200:
              description: Ok
            403:
              description: Not started
            404:
              description: Can't find safe path.
    """

    assert _dobot is not None

    if not isinstance(request.json, dict):
        raise FlaskException("Body should be a JSON dict containing Pose.", error_code=400)

    pose = Pose.from_dict(request.json)
    move_type = MoveType(request.args.get("moveType", "jump"))
    velocity = float(request.args.get("velocity", default=50.0))
    acceleration = float(request.args.get("acceleration", default=50.0))
    safe = request.args.get("safe") == "true"

    if safe:
        cp = _dobot.get_end_effector_pose()

        ip1 = copy.deepcopy(cp)
        ip2 = copy.deepcopy(pose)

        for _attempt in range(20):
            res = scene_service.line_check(LineCheck(ip1.position, ip2.position))

            if res.safe:
                break

            if move_type == MoveType.LINEAR:
                raise FlaskException("There might be a collision.", error_code=400)

            ip1.position.z += 0.01
            ip2.position.z += 0.01

        else:
            return "Can't find safe path.", 404

        logger.debug(f"Collision avoidance attempts: {_attempt}")

        if _attempt > 0:
            _dobot.move(ip1, move_type, velocity, acceleration)
            _dobot.move(ip2, move_type, velocity, acceleration)

    _dobot.move(pose, move_type, velocity, acceleration)
    return Response(status=204)


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
            204:
              description: Ok
            403:
              description: Not started
    """

    assert _dobot is not None
    _dobot.home()
    return Response(status=204)


@app.route("/hand_teaching", methods=["GET"])
@requires_started
def get_hand_teaching() -> RespT:
    """Get hand teaching status.
    ---
    get:
        description: Get hand teaching status.
        tags:
           - Robot
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

    assert _dobot
    return jsonify(_dobot.hand_teaching_mode)


@app.route("/hand_teaching", methods=["PUT"])
@requires_started
def put_hand_teaching() -> RespT:
    """Set hand teaching status.
    ---
    put:
        description: Set hand teaching status.
        tags:
           - Robot
        parameters:
            - in: query
              name: enabled
              schema:
                type: boolean
        responses:
            204:
              description: Ok
            403:
              description: Not started
    """

    assert _dobot
    _dobot.hand_teaching_mode = request.args.get("enabled") == "true"
    return Response(status=204)


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
            204:
              description: Ok
            403:
              description: Not started
    """

    assert _dobot is not None
    _dobot.suck()
    return Response(status=204)


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
            204:
              description: Ok
            403:
              description: Not started
    """

    assert _dobot is not None
    _dobot.release()
    return Response(status=204)


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
    return jsonify(_dobot.robot_joints())


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

    if not isinstance(request.json, dict):
        raise FlaskException("Body should be a JSON dict containing Pose.", error_code=400)

    pose = Pose.from_dict(request.json)
    return jsonify(_dobot.inverse_kinematics(pose))


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

    if not isinstance(request.json, list):
        raise FlaskException("Body should be a JSON array containing joints.", error_code=400)

    joints = [Joint.from_dict(j) for j in request.json]
    return jsonify(_dobot.forward_kinematics(joints))


@app.errorhandler(DobotApiException)  # type: ignore  # TODO what's wrong?
def handle_dobot_exception(e: DobotApiException) -> tuple[str, int]:
    return json.dumps(str(e)), 400


def main() -> None:

    parser = argparse.ArgumentParser(description=SERVICE_NAME)
    parser.add_argument("-s", "--swagger", action="store_true", default=False)
    parser.add_argument("-m", "--mock", action="store_true", default=env.get_bool("ARCOR2_DOBOT_MOCK"))

    parser.add_argument(
        "-d",
        "--debug",
        help="Set logging level to debug.",
        action="store_const",
        const=logging.DEBUG,
        default=logging.DEBUG if env.get_bool("ARCOR2_DOBOT_DEBUG") else logging.INFO,
    )

    args = parser.parse_args()
    logger.setLevel(args.debug)

    global _mock
    _mock = args.mock
    if _mock:
        logger.info("Starting as a mock!")

    if not args.swagger:
        scene_service.wait_for()

    run_app(app, SERVICE_NAME, version(), port_from_url(URL), [Pose, Joint], args.swagger)

    if _dobot:
        _dobot.cleanup()


if __name__ == "__main__":
    main()
