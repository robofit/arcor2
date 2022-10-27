import argparse
import copy
import logging
import math
import os
import socket
import time
from dataclasses import dataclass
from functools import wraps
from threading import Lock, Thread

import requests
from fanucpy import Robot
from flask import Response, jsonify, request

from arcor2 import env
from arcor2 import transformations as tr
from arcor2.clients import scene_service
from arcor2.data.common import Joint, Orientation, Pose, Position
from arcor2.data.scene import LineCheck
from arcor2.exceptions import Arcor2Exception
from arcor2.flask import RespT, create_app, run_app
from arcor2.helpers import port_from_url
from arcor2.logging import get_logger
from arcor2_fanuc import version
from arcor2_fanuc.exceptions import FanucGeneral, NotFound, StartError, WebApiError

logger = get_logger(__name__)

SERVICE_NAME = os.getenv("ARCOR2_FANUC_SERVICE_NAME", "Fanuc Web API")
URL = os.getenv("ARCOR2_FANUC_SERVICE_URL", "http://localhost:5027")
ROBOT_HOST = os.getenv("ARCOR2_FANUC_ROBOT_HOST", "192.168.104.140")
ROBOT_PORT = env.get_int("ARCOR2_FANUC_ROBOT_PORT", 18735)
EEF_DO_NUM = env.get_int("ARCOR2_FANUC_EEF_DO_NUM", 1)
MAX_VELOCITY = env.get_int("ARCOR2_FANUC_MAX_VELOCITY", 6000)
MAX_ACCELERATION = env.get_int("ARCOR2_FANUC_MAX_ACCELERATION", 100)
Z_AXIS_OFFSET = env.get_float("ARCOR2_FANUC_Z_AXIS_OFFSET", 330.0)  # world origin is at j1/j2

app = create_app(__name__)


class ThreadSafeRobot(Robot):
    def __init__(self, *args, **kwargs):

        super().__init__(*args, **kwargs)
        self._socket_lock = Lock()
        self._session = requests.session()
        self._pos_joints_thread = Thread(target=self._pos_joints_thread_run, args=())
        self._pos_joints_thread.daemon = True
        self._running = True

        self._data_lock = Lock()
        self._req_rate = 0.1
        self._cur_pos: list[float] = [0] * 6
        self._cur_joints: list[float] = [0] * 6

    def connect(self) -> None:

        try:
            res = self._session.get(f"http://{ROBOT_HOST}/MD/PRGSTATE.DG")
        except requests.RequestException:
            logger.exception(f"Failed to contact robot at {ROBOT_HOST}.")
            raise Arcor2Exception("Failed to contact robot.")

        for line in res.text.splitlines():

            # MAPPDK_SERVER RUNNING @ 49 in OPEN_COMM of MAPPDK_SERVER
            # MAPPDK_SERVER RUNNING @ 61 in MAPPDK_SERVER of MAPPDK_SERVER
            # MAPPDK_SERVER status = ABORTED

            if "MAPPDK_SERVER" in line:
                if "RUNNING" in line:
                    if "OPEN_COMM" not in line:
                        raise Arcor2Exception("Someone is already connected to the robot.")
                    break  # good!
                elif "ABORTED" in line:
                    raise Arcor2Exception("MAPPDK not running.")
                else:
                    raise Arcor2Exception("MAPPDK - unhandled state.")
        else:
            raise Arcor2Exception("MAPPDK program not found.")

        super().connect()
        self._pos_joints_thread.start()

    def _pos_joints_thread_run(self) -> None:

        last = time.monotonic()
        logger.info("Position/joints thread started.")

        while self._running:

            pos: list[float] = []
            joints: list[float] = []
            found = False

            r = self._session.get(f"http://{ROBOT_HOST}/MD/CURPOS.DG")

            for line in r.text.splitlines():

                if len(joints) < 6 and line.startswith("Joint"):
                    joints.append(float(line.split(" ")[-1]))

                if len(pos) < 6:

                    if line.startswith("CURRENT WORLD POSITION"):
                        found = True
                    if not found:
                        continue

                    if line[1] == ":":
                        pos.append(float(line.split(" ")[-1]))

                if len(joints) == 6 and len(pos) == 6:
                    break

            assert len(pos) == 6
            assert len(joints) == 6

            with self._data_lock:
                self._cur_pos = pos
                self._cur_joints = joints

            now = time.monotonic()
            time_to_sleep = max(self._req_rate - (now - last), 0)
            # logger.debug(f"The actual stuff took: {now - last:.3f}s, going to sleep for {time_to_sleep:.3f}s.")
            time.sleep(time_to_sleep)
            last = time.monotonic()

        logger.info("Position/joints thread finished.")

    def disconnect(self) -> None:
        self._running = False
        super().disconnect()

    def get_curpos(self) -> list[float]:
        with self._data_lock:
            return self._cur_pos.copy()

    def get_curjpos(self) -> list[float]:
        with self._data_lock:
            return self._cur_joints.copy()

    def send_cmd(self, cmd):

        try:
            with self._socket_lock:
                return super().send_cmd(cmd)
        except socket.timeout:
            logger.exception("Communication with the robot timeouted.")
            raise Arcor2Exception("Robot not responding.")
        except OSError:
            logger.exception("Socket broken?")
            raise Arcor2Exception("Connection with the robot broken.")
        except Exception as e:

            if str(e).strip() == "position-is-not-reachable":
                raise Arcor2Exception("Position not reachable.")

            logger.exception("Some bad dirty exception...")

            raise Arcor2Exception(str(e)) from e


@dataclass
class Globals:

    robot: None | ThreadSafeRobot = None
    pose: Pose = Pose()


gl = Globals()


def vals_to_pose(vals: list[float]) -> Pose:

    assert len(vals) == 6

    # https://doc.rc-cube.com/v21.10/en/pose_format_fanuc.html
    wr = math.radians(vals[3])
    pr = math.radians(vals[4])
    rr = math.radians(vals[5])

    x = math.cos(rr / 2) * math.cos(pr / 2) * math.sin(wr / 2) - math.sin(rr / 2) * math.sin(pr / 2) * math.cos(wr / 2)
    y = math.cos(rr / 2) * math.sin(pr / 2) * math.cos(wr / 2) + math.sin(rr / 2) * math.cos(pr / 2) * math.sin(wr / 2)
    z = math.sin(rr / 2) * math.cos(pr / 2) * math.cos(wr / 2) - math.cos(rr / 2) * math.sin(pr / 2) * math.sin(wr / 2)
    w = math.cos(rr / 2) * math.cos(pr / 2) * math.cos(wr / 2) + math.sin(rr / 2) * math.sin(pr / 2) * math.sin(wr / 2)

    return Pose(
        Position(vals[0] / 1000.0, vals[1] / 1000.0, (vals[2] + Z_AXIS_OFFSET) / 1000.0), Orientation(x, y, z, w)
    )


def pose_to_vals(pose: Pose) -> list[float]:

    # https://doc.rc-cube.com/v21.10/en/pose_format_fanuc.html
    # ...P and W are swapped!
    w = math.degrees(
        math.atan2(
            2 * (pose.orientation.w * pose.orientation.z + pose.orientation.x * pose.orientation.y),
            1 - 2 * (pose.orientation.y**2 + pose.orientation.z**2),
        )
    )
    p = math.degrees(math.asin(2 * (pose.orientation.w * pose.orientation.y - pose.orientation.z * pose.orientation.x)))
    r = math.degrees(
        math.atan2(
            2 * (pose.orientation.w * pose.orientation.x + pose.orientation.y * pose.orientation.z),
            1 - 2 * (pose.orientation.x**2 + pose.orientation.y**2),
        )
    )

    pos: list[float] = [pose.position.x * 1000, pose.position.y * 1000, pose.position.z * 1000 - Z_AXIS_OFFSET]
    pos.extend([r, p, w])

    assert len(pos) == 6

    return pos


def started() -> bool:

    return gl.robot is not None


def requires_started(f):
    @wraps(f)
    def wrapped(*args, **kwargs):
        if not started():
            raise StartError("Not started.")
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
        requestBody:
              content:
                application/json:
                  schema:
                    $ref: Pose
        responses:
            204:
              description: Ok
            500:
              description: "Error types: **General**, **FanucGeneral**, **StartError**."
              content:
                application/json:
                  schema:
                    $ref: WebApiError
    """

    if started():
        raise StartError("Already started.")

    if not isinstance(request.json, dict):
        raise FanucGeneral("Body should be a JSON dict containing Pose.")

    pose = Pose.from_dict(request.json)

    robot = ThreadSafeRobot("Fanuc", ROBOT_HOST, ROBOT_PORT, ee_DO_type="RDO", ee_DO_num=EEF_DO_NUM)

    try:
        robot.connect()
    except ConnectionRefusedError as e:
        logger.error(f"Failed to connect to {ROBOT_HOST}:{ROBOT_PORT}. {str(e)}")
        raise FanucGeneral("Maybe the robot is not running?")

    gl.robot = robot
    gl.pose = pose

    logger.info(f"Robot initialized at {pose}")

    # TODO illegal port number
    # gl.robot.gripper(gl.gripper)  # open a gripper, so we have a known state

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
            500:
              description: "Error types: **General**."
              content:
                application/json:
                  schema:
                    $ref: WebApiError
    """

    assert gl.robot is not None
    gl.robot.disconnect()
    gl.robot = None
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
            500:
              description: "Error types: **General**, **StartError**."
              content:
                application/json:
                  schema:
                    $ref: WebApiError
    """

    return jsonify(started())


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
            500:
              description: "Error types: **General**."
              content:
                application/json:
                  schema:
                    $ref: WebApiError
    """

    assert gl.robot is not None
    return jsonify(tr.make_pose_abs(gl.pose, vals_to_pose(gl.robot.get_curpos()))), 200


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
            - name: velocity
              in: query
              schema:
                type: number
                format: integer
                minimum: 0
                maximum: 100
            - name: acceleration
              in: query
              schema:
                type: number
                format: integer
                minimum: 0
                maximum: 100
            - name: cnt_val
              in: query
              schema:
                type: number
                format: integer
                minimum: 0
                maximum: 100
            - in: query
              name: linear
              schema:
                type: boolean
                default: false
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
            204:
              description: Ok
            500:
              description: "Error types: **General**, **FanucGeneral**, **StartError**, **NotFound**."
              content:
                application/json:
                  schema:
                    $ref: WebApiError
    """

    assert gl.robot is not None

    if not isinstance(request.json, dict):
        raise FanucGeneral("Body should be a JSON dict containing Pose.")

    abs_pose = Pose.from_dict(request.json)
    pose = tr.make_pose_rel(gl.pose, abs_pose)
    velocity = int(float(request.args.get("velocity", default=50))) * MAX_VELOCITY / 100
    acceleration = int(float(request.args.get("acceleration", default=50))) * MAX_ACCELERATION / 100
    cnt_val = int(float(request.args.get("cnt_val", default=50)))
    linear = request.args.get("linear") == "true"
    safe = request.args.get("safe") == "true"

    logger.info(f"Moving to {pose}, velocity: {velocity}, acceleration: {acceleration}, linear: {linear}, safe: {safe}")

    if safe:
        cp = tr.make_pose_abs(gl.pose, vals_to_pose(gl.robot.get_curpos()))

        ip1 = copy.deepcopy(cp)
        ip2 = copy.deepcopy(abs_pose)

        for _attempt in range(20):
            res = scene_service.line_check(LineCheck(ip1.position, ip2.position))

            if res.safe:
                break

            if linear:
                raise FanucGeneral("There might be a collision.")

            ip1.position.z += 0.01
            ip2.position.z += 0.01

        else:
            raise NotFound("Can't find safe path.")

        logger.debug(f"Collision avoidance attempts: {_attempt}")

        if _attempt > 0:
            gl.robot.move("pose", pose_to_vals(tr.make_pose_rel(gl.pose, ip1)), velocity, acceleration, cnt_val, linear)
            gl.robot.move("pose", pose_to_vals(tr.make_pose_rel(gl.pose, ip2)), velocity, acceleration, cnt_val, linear)

    logger.debug(f"curpos: {gl.robot.get_curpos()}")
    logger.debug(f"tarpos: {pose_to_vals(pose)}")

    gl.robot.move("pose", pose_to_vals(pose), velocity, acceleration, cnt_val, linear)
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
            500:
              description: "Error types: **General**, **StartError**."
              content:
                application/json:
                  schema:
                    $ref: WebApiError
    """

    assert gl.robot is not None
    joints = gl.robot.get_curjpos()

    # see https://www.robot-forum.com/robotforum/thread/22888-fanuc-j2-j3-relationship/ for explanation
    joints[2] += joints[1]

    return jsonify([Joint(f"joint_{idx+1}", math.radians(value)).to_dict() for idx, value in enumerate(joints)])


@app.route("/gripper", methods=["PUT"])
@requires_started
def put_gripper() -> RespT:
    """Controls the gripper.
    ---
    put:
        description: Controls the gripper.
        tags:
           - Robot
        parameters:
            - in: query
              name: state
              schema:
                type: boolean
                default: false
        responses:
            204:
              description: Ok
            500:
              description: "Error types: **General**, **StartError**."
              content:
                application/json:
                  schema:
                    $ref: WebApiError
    """

    assert gl.robot is not None

    state = request.args.get("state") == "true"
    logger.info(f"{'Opening' if state else 'Closing'} the gripper.")
    gl.robot.gripper(state)
    return Response(status=204)


@app.route("/gripper", methods=["GET"])
@requires_started
def get_gripper() -> RespT:
    """Get gripper state.
    ---
    put:
        description: Get gripper state.
        tags:
           - Robot
        responses:
            200:
              description: Ok
              content:
                application/json:
                    schema:
                        type: boolean
            500:
              description: "Error types: **General**, **StartError**."
              content:
                application/json:
                  schema:
                    $ref: WebApiError
    """

    assert gl.robot is not None
    return jsonify(bool(gl.robot.get_rdo(EEF_DO_NUM)))


def main() -> None:

    parser = argparse.ArgumentParser(description=SERVICE_NAME)
    parser.add_argument("-s", "--swagger", action="store_true", default=False)

    parser.add_argument(
        "-d",
        "--debug",
        help="Set logging level to debug.",
        action="store_const",
        const=logging.DEBUG,
        default=logging.DEBUG if env.get_bool("ARCOR2_FANUC_DEBUG") else logging.INFO,
    )

    args = parser.parse_args()
    logger.setLevel(args.debug)

    if not args.swagger:
        scene_service.wait_for()

    run_app(app, SERVICE_NAME, version(), port_from_url(URL), [Pose, Joint, WebApiError], args.swagger)

    if gl.robot:
        gl.robot.disconnect()


if __name__ == "__main__":
    main()
