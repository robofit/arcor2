#!/usr/bin/env python3

import argparse
import logging
import os
import threading
import time
from dataclasses import dataclass, field
from functools import wraps

import rclpy  # pants: no-infer-dep
from ament_index_python.packages import get_package_share_directory  # pants: no-infer-dep
from flask import Response, jsonify, request
from geometry_msgs.msg import Pose as RosPose  # pants: no-infer-dep
from geometry_msgs.msg import PoseStamped  # pants: no-infer-dep
from moveit.planning import MoveItPy, PlanningComponent  # pants: no-infer-dep
from moveit_configs_utils import MoveItConfigsBuilder  # pants: no-infer-dep
from rclpy.callback_groups import MutuallyExclusiveCallbackGroup  # pants: no-infer-dep
from rclpy.node import Node  # pants: no-infer-dep
from rclpy.qos import QoSDurabilityPolicy, QoSProfile, QoSReliabilityPolicy  # pants: no-infer-dep
from sensor_msgs.msg import JointState  # pants: no-infer-dep
from std_msgs.msg import Bool, String  # pants: no-infer-dep
from std_srvs.srv import Trigger  # pants: no-infer-dep
from tf2_geometry_msgs import do_transform_pose  # pants: no-infer-dep
from tf2_ros.buffer import Buffer  # pants: no-infer-dep
from tf2_ros.transform_listener import TransformListener  # pants: no-infer-dep
from ur_dashboard_msgs.msg import RobotMode  # pants: no-infer-dep
from ur_dashboard_msgs.srv import Load  # pants: no-infer-dep
from ur_msgs.srv import SetPayload, SetSpeedSliderFraction  # pants: no-infer-dep

from arcor2 import env
from arcor2 import transformations as tr
from arcor2.data.common import Joint, Pose
from arcor2.data.robot import InverseKinematicsRequest
from arcor2.flask import RespT, create_app, run_app
from arcor2.helpers import port_from_url
from arcor2.logging import get_logger
from arcor2_ur import get_data, topics, version
from arcor2_ur.exceptions import StartError, UrGeneral, WebApiError
from arcor2_ur.object_types.ur5e import Vacuum
from arcor2_ur.vgc10 import VGC10

logger = get_logger(__name__)

URL = os.getenv("ARCOR2_UR_URL", "http://localhost:5012")
BASE_LINK = os.getenv("ARCOR2_UR_BASE_LINK", "base_link")
TOOL_LINK = os.getenv("ARCOR2_UR_TOOL_LINK", "tool0")
UR_TYPE = os.getenv("ARCOR2_UR_TYPE", "ur5e")
PLANNING_GROUP_NAME = os.getenv("ARCOR2_UR_PLANNING_GROUP_NAME", "ur_manipulator")
ROBOT_IP = os.getenv("ARCOR2_UR_ROBOT_IP", "")
VGC10_PORT = env.get_int("ARCOR2_UR_VGC10_PORT", 54321)
INTERACT_WITH_DASHBOARD = env.get_bool("ARCOR2_UR_INTERACT_WITH_DASHBOARD", True)

SERVICE_NAME = f"UR Web API ({UR_TYPE})"


def plan_and_execute(
    robot,
    planning_component,
    logger,
    single_plan_parameters=None,
    multi_plan_parameters=None,
    sleep_time=0.0,
) -> None:
    """Helper function to plan and execute a motion."""
    # plan to goal
    logger.info("Planning trajectory")
    if multi_plan_parameters is not None:
        plan_result = planning_component.plan(multi_plan_parameters=multi_plan_parameters)
    elif single_plan_parameters is not None:
        plan_result = planning_component.plan(single_plan_parameters=single_plan_parameters)
    else:
        plan_result = planning_component.plan()

    # execute the plan
    if plan_result:
        logger.info("Executing plan")
        robot_trajectory = plan_result.trajectory
        if not robot.execute(robot_trajectory, controllers=[]):
            raise UrGeneral("Trajectory execution failed.")
    else:
        raise UrGeneral("Planning failed")  # TODO raise more specific exception

    time.sleep(sleep_time)


class MyNode(Node):
    def __init__(self, interact_with_dashboard=True) -> None:
        super().__init__("ur_api_node", enable_logger_service=True)
        if globs.debug:
            # TODO makes no difference for moveitpy :-/
            rclpy.logging.set_logger_level("ur_api_node", rclpy.logging.LoggingSeverity.DEBUG)

        sub_qos = QoSProfile(
            depth=1, durability=QoSDurabilityPolicy.TRANSIENT_LOCAL, reliability=QoSReliabilityPolicy.RELIABLE
        )

        self.buffer = Buffer()
        self.listener = TransformListener(self.buffer, self)
        self.subscription = self.create_subscription(
            JointState, "joint_states", self.joint_states_cb, 10, callback_group=MutuallyExclusiveCallbackGroup()
        )
        self.interact_with_dashboard = interact_with_dashboard

        self.robot_mode: RobotMode | None = None
        self.robot_program_running: bool | None = None

        self._break_release_client = self.create_client(Trigger, topics.BRAKE_RELEASE_SRV)
        self._power_off_client = self.create_client(Trigger, topics.POWER_OFF_SRV)
        self._load_program_client = self.create_client(Load, topics.LOAD_PROGRAM_SRV)
        self._play_client = self.create_client(Trigger, topics.PLAY_SRV)
        self._set_speed_slider_client = self.create_client(SetSpeedSliderFraction, topics.SET_SPEED_SLIDER_SRV)
        self._set_payload_client = self.create_client(SetPayload, topics.SET_PAYLOAD_SRV)

        self.script_cmd_pub = self.create_publisher(String, "/urscript_interface/script_command", 10)
        self.robot_mode_sub = self.create_subscription(
            RobotMode,
            topics.ROBOT_MODE_TOPIC,
            self.robot_mode_cb,
            sub_qos,
            callback_group=MutuallyExclusiveCallbackGroup(),
        )
        self.robot_program_running_sub = self.create_subscription(
            Bool,
            topics.ROBOT_PROGRAM_RUNNING_TOPIC,
            self.robot_program_running_cb,
            sub_qos,
            callback_group=MutuallyExclusiveCallbackGroup(),
        )

    def wait_for_services(self) -> None:
        while self.interact_with_dashboard and not self._break_release_client.wait_for_service(timeout_sec=1.0):
            logger.warning(f"Service {topics.BRAKE_RELEASE_SRV} not available, waiting again...")

        while self.interact_with_dashboard and not self._power_off_client.wait_for_service(timeout_sec=1.0):
            logger.warning(f"Service {topics.POWER_OFF_SRV} not available, waiting again...")

        while self.interact_with_dashboard and not self._load_program_client.wait_for_service(timeout_sec=1.0):
            logger.warning(f"Service {topics.LOAD_PROGRAM_SRV} not available, waiting again...")

        while self.interact_with_dashboard and not self._play_client.wait_for_service(timeout_sec=1.0):
            logger.warning(f"Service {topics.PLAY_SRV} not available, waiting again...")

        while not self._set_speed_slider_client.wait_for_service(timeout_sec=1.0):
            logger.warning(f"Service {topics.SET_SPEED_SLIDER_SRV} not available, waiting again...")

        while not self._set_payload_client.wait_for_service(timeout_sec=1.0):
            logger.warning(f"Service {topics.SET_PAYLOAD_SRV} not available, waiting again...")

    def robot_program_running_cb(self, msg: Bool) -> None:
        logger.info(f"Program running: {msg.data}")
        self.robot_program_running = msg.data

    def robot_mode_cb(self, msg: RobotMode) -> None:
        logger.info(f"Robot mode: {msg.mode}")
        self.robot_mode = msg

    def wait_for_robot_mode(self, mode: set[RobotMode], timeout=30) -> None:
        start = time.monotonic()
        while self.robot_mode is None or self.robot_mode.mode not in mode:
            time.sleep(0.1)
            if time.monotonic() - start > timeout:
                raise TimeoutError(f"Timeout when waiting for RobotMode={mode}.")

    def wait_for_program_running(self, timeout=10) -> None:
        start = time.monotonic()
        while not self.robot_program_running:
            time.sleep(0.1)
            if time.monotonic() - start > timeout:
                raise TimeoutError("Timeout when waiting for program running.")

    def urscript(self, src: str) -> None:
        msg = String()
        msg.data = src
        self.script_cmd_pub.publish(msg)

    def brake_release(self) -> None:
        if not self.interact_with_dashboard:
            return

        future = self._break_release_client.call_async(Trigger.Request())
        rclpy.spin_until_future_complete(self, future, timeout_sec=2)

        if future.result() is None:
            raise UrGeneral("Service call failed!")

        response = future.result()
        if not response.success:
            raise UrGeneral(f"Service call failed with message: {response.message}")

    def power_off(self) -> None:
        if not self.interact_with_dashboard:
            return

        future = self._power_off_client.call_async(Trigger.Request())
        rclpy.spin_until_future_complete(self, future, timeout_sec=2)

        if future.result() is None:
            raise UrGeneral("Service call failed!")

        response = future.result()
        if not response.success:
            raise UrGeneral(f"Service call failed with message: {response.message}")

    def load_program(self) -> None:
        if not self.interact_with_dashboard:
            return

        future = self._load_program_client.call_async(Load.Request(filename="prog.urp"))
        rclpy.spin_until_future_complete(self, future, timeout_sec=2)

        if future.result() is None:
            raise UrGeneral("Service call failed!")

        response = future.result()
        if not response.success:
            raise UrGeneral(f"Service call failed with message: {response.answer}")

    def play(self) -> None:
        if not self.interact_with_dashboard:
            return

        future = self._play_client.call_async(Trigger.Request())
        rclpy.spin_until_future_complete(self, future, timeout_sec=2)

        if future.result() is None:
            raise UrGeneral("Service call failed!")

        response = future.result()
        if not response.success:
            raise UrGeneral(f"Service call failed with message: {response.message}")

    def set_speed_slider(self, value: float):
        if value <= 0 or value > 1:
            raise UrGeneral("Invalid speed.")

        future = self._set_speed_slider_client.call_async(SetSpeedSliderFraction.Request(speed_slider_fraction=value))
        rclpy.spin_until_future_complete(self, future, timeout_sec=2)

        if future.result() is None:
            raise UrGeneral("Service call failed!")

        response = future.result()
        if not response.success:
            raise UrGeneral(f"Service call failed (speed: {value}).")

    def set_payload(self, value: float):
        if value < 0:
            raise UrGeneral("Invalid payload.")

        future = self._set_payload_client.call_async(SetPayload.Request(mass=value))
        rclpy.spin_until_future_complete(self, future, timeout_sec=2)

        if future.result() is None:
            raise UrGeneral("Service call failed!")

        response = future.result()
        if not response.success:
            raise UrGeneral("Service call failed.")

    def joint_states_cb(self, msg: JointState) -> None:
        if globs.state is not None:
            # TODO not very clean solution
            globs.state.joints = [Joint(name, position) for name, position in zip(msg.name, msg.position)]


@dataclass
class State:
    pose: Pose
    node: MyNode
    executor: rclpy.executors.MultiThreadedExecutor
    executor_thread: threading.Thread
    moveitpy: MoveItPy
    ur_manipulator: PlanningComponent
    joints: list[Joint] = field(default_factory=list)
    tool: VGC10 | None = None

    def shutdown(self) -> None:
        if self.tool:
            self.tool.release_vacuum()
            self.tool.close_connection()

        self.node.destroy_node()
        self.executor.shutdown()
        self.executor_thread.join(3)
        assert not self.executor_thread.is_alive()
        self.moveitpy.shutdown()
        rclpy.shutdown()

    def __post_init__(self) -> None:
        if self.tool:
            self.tool.open_connection()


@dataclass
class Globs:
    debug = False
    state: State | None = None
    # lock: threading.Lock = threading.Lock()


globs: Globs = Globs()
app = create_app(__name__)

# this is normally specified in a launch file
moveit_config = (
    MoveItConfigsBuilder(robot_name="ur", package_name="ur_moveit_config")
    .robot_description(
        os.path.join(get_package_share_directory("ur_description"), "urdf", "ur.urdf.xacro"),
        {"name": "ur", "ur_type": UR_TYPE},
    )
    .robot_description_semantic(
        os.path.join(get_package_share_directory("ur_moveit_config"), "srdf", "ur.srdf.xacro"), {"name": UR_TYPE}
    )
    .trajectory_execution(
        os.path.join(get_package_share_directory("ur_moveit_config"), "config", "moveit_controllers.yaml")
    )
    .robot_description_kinematics(
        os.path.join(get_package_share_directory("ur_moveit_config"), "config", "kinematics.yaml")
    )
    .moveit_cpp(file_path=get_data("moveit.yaml"))
    .to_moveit_configs()
).to_dict()


def started() -> bool:
    return globs.state is not None


def requires_started(f):
    @wraps(f)
    def wrapped(*args, **kwargs):
        if not started():
            raise StartError("Not started")
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
              description: "Error types: **General**, **UrGeneral**, **StartError**."
              content:
                application/json:
                  schema:
                    $ref: WebApiError
    """

    if started():
        raise StartError("Already started.")

    if not isinstance(request.json, dict):
        raise UrGeneral("Body should be a JSON dict containing Pose.")

    pose = Pose.from_dict(request.json)

    rclpy.init()
    node = MyNode(INTERACT_WITH_DASHBOARD)
    executor = rclpy.executors.MultiThreadedExecutor()
    executor.add_node(node)
    executor_thread = threading.Thread(target=executor.spin, daemon=True)
    executor_thread.start()

    node.wait_for_services()

    try:
        node.brake_release()
        node.wait_for_robot_mode({RobotMode.RUNNING, RobotMode.IDLE})
        node.load_program()
        node.play()
        node.wait_for_program_running()

    except Exception:
        node.destroy_node()
        rclpy.shutdown()
        raise

    vgc10: VGC10 | None = None
    if ROBOT_IP:
        vgc10 = VGC10(ROBOT_IP, VGC10_PORT)

    moveitpy = MoveItPy(node_name="moveit_py", config_dict=moveit_config)
    globs.state = State(
        pose,
        node,
        executor,
        executor_thread,
        moveitpy,
        moveitpy.get_planning_component(PLANNING_GROUP_NAME),
        tool=vgc10,
    )

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
              description: "Error types: **General**, **StartError**."
              content:
                application/json:
                  schema:
                    $ref: WebApiError
    """

    assert globs.state

    globs.state.node.power_off()
    globs.state.shutdown()
    globs.state = None

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
              description: "Error types: **General**."
              content:
                application/json:
                  schema:
                    $ref: WebApiError
    """

    return jsonify(started())


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

    assert globs.state

    return jsonify([joint.to_dict() for joint in globs.state.joints])


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
                    $ref: InverseKinematicsRequest
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
              description: "Error types: **General**, **DobotGeneral**, **StartError**."
              content:
                application/json:
                  schema:
                    $ref: WebApiError
    """

    assert globs.state

    if not isinstance(request.json, dict):
        raise UrGeneral("Body should be a JSON dict containing InverseKinematicsRequest.")

    ikr = InverseKinematicsRequest.from_dict(request.json)

    if not ikr.start_joints:
        ikr.start_joints = globs.state.joints
    elif len(ikr.start_joints) != len(globs.state.joints):
        raise UrGeneral(f"Wrong number of joints! Should be {len(globs.state.joints)}.")

    ikr.pose = tr.make_pose_rel(globs.state.pose, ikr.pose)

    logger.debug(f"Got IK request: {ikr}")

    with globs.state.moveitpy.get_planning_scene_monitor().read_write() as scene:
        if not ikr.avoid_collisions:
            scene.remove_all_collision_objects()

        scene.current_state.update(force=True)

        scene.current_state.joint_positions = {j.name: j.value for j in ikr.start_joints}

        pose_goal = RosPose()
        pose_goal.position.x = ikr.pose.position.x
        pose_goal.position.y = ikr.pose.position.y
        pose_goal.position.z = ikr.pose.position.z
        pose_goal.orientation.x = ikr.pose.orientation.x
        pose_goal.orientation.y = ikr.pose.orientation.y
        pose_goal.orientation.z = ikr.pose.orientation.z
        pose_goal.orientation.w = ikr.pose.orientation.w

        # Set the robot state and check collisions
        if not scene.current_state.set_from_ik(PLANNING_GROUP_NAME, pose_goal, TOOL_LINK, timeout=3):
            raise UrGeneral("Can't get IK!")

        scene.current_state.update()  # required to update transforms

        if (
            scene.is_state_colliding(
                robot_state=scene.current_state, joint_model_group_name=PLANNING_GROUP_NAME, verbose=True
            )
            and ikr.avoid_collisions
        ):
            raise UrGeneral("State is in collision.")  # TODO IK exception...

        assert len(scene.current_state.joint_positions) == len(globs.state.joints)

        return jsonify([Joint(jn, jv).to_dict() for jn, jv in scene.current_state.joint_positions.items()])


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
              description: "Error types: **General**, **StartError**."
              content:
                application/json:
                  schema:
                    $ref: WebApiError
    """

    assert globs.state

    ps = RosPose()

    time = rclpy.time.Time()

    globs.state.node.buffer.can_transform(BASE_LINK, TOOL_LINK, time, timeout=rclpy.time.Duration(seconds=1.0))
    transform = globs.state.node.buffer.lookup_transform(BASE_LINK, TOOL_LINK, time)
    pst = do_transform_pose(ps, transform)

    pose = Pose()
    pose.position.x = pst.position.x
    pose.position.y = pst.position.y
    pose.position.z = pst.position.z

    pose.orientation.x = pst.orientation.x
    pose.orientation.y = pst.orientation.y
    pose.orientation.z = pst.orientation.z
    pose.orientation.w = pst.orientation.w

    pose = tr.make_pose_abs(globs.state.pose, pose)

    return jsonify(pose.to_dict()), 200


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
                format: float
                minimum: 0
                maximum: 100
                default: 50
            - name: payload
              in: query
              schema:
                type: number
                format: float
                minimum: 0
                maximum: 5
                default: 0
        requestBody:
              content:
                application/json:
                  schema:
                    $ref: Pose
        responses:
            200:
              description: Ok
            500:
              description: "Error types: **General**, **UrGeneral**, **StartError**, **NotFound**."
              content:
                application/json:
                  schema:
                    $ref: WebApiError
    """

    assert globs.state

    if not isinstance(request.json, dict):
        raise UrGeneral("Body should be a JSON dict containing Pose.")

    pose = Pose.from_dict(request.json)
    velocity = float(request.args.get("velocity", default=50.0)) / 100.0
    payload = float(request.args.get("payload", default=0.0))

    pose = tr.make_pose_rel(globs.state.pose, pose)

    pose_goal = PoseStamped()
    pose_goal.header.frame_id = BASE_LINK

    pose_goal.pose.orientation.x = pose.orientation.x
    pose_goal.pose.orientation.y = pose.orientation.y
    pose_goal.pose.orientation.z = pose.orientation.z
    pose_goal.pose.orientation.w = pose.orientation.w
    pose_goal.pose.position.x = pose.position.x
    pose_goal.pose.position.y = pose.position.y
    pose_goal.pose.position.z = pose.position.z

    with globs.state.moveitpy.get_planning_scene_monitor().read_write() as scene:
        scene.current_state.update(force=True)
        scene.current_state.joint_positions = {j.name: j.value for j in globs.state.joints}
        scene.current_state.update()

    globs.state.ur_manipulator.set_start_state_to_current_state()
    globs.state.ur_manipulator.set_goal_state(pose_stamped_msg=pose_goal, pose_link=TOOL_LINK)

    globs.state.node.set_speed_slider(velocity)
    globs.state.node.set_payload(payload)

    plan_and_execute(globs.state.moveitpy, globs.state.ur_manipulator, logger)

    return Response(status=204)


@app.route("/suction/suck", methods=["PUT"])
@requires_started
def put_suck() -> RespT:
    """Turn on suction.
    ---
    put:
        description: Get the current state.
        tags:
           - Tool
        parameters:
            - name: vacuum
              in: query
              schema:
                type: integer
                minimum: 0
                maximum: 80
                default: 60
              description: Tells how hard to grasp in the range of 0% to 80 % vacuum.
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

    assert globs.state

    if not globs.state.tool:
        # "simulate" the tool when not configured (e.g. when using with simulation)
        logger.warning("PUT /suction/suck called while a tool is not configured.")
        return Response(status=204)

    vacuum = int(request.args.get("vacuum", default=60))
    globs.state.tool.vacuum_on(vacuum)

    return Response(status=204)


@app.route("/suction/vacuum", methods=["GET"])
@requires_started
def get_vacuum() -> RespT:
    """Gets vacuum value.
    ---
    get:
        description: Get the measured vacuum.
        tags:
           - Tool
        responses:
            200:
              description: Returns current relative vacuum on each channel.
              content:
                application/json:
                  schema:
                    $ref: Vacuum
            500:
              description: "Error types: **General**, **StartError**."
              content:
                application/json:
                  schema:
                    $ref: WebApiError
    """

    assert globs.state

    if not globs.state.tool:
        # "simulate" the tool when not configured (e.g. when using with simulation)
        logger.warning("PUT /suction/vacuum called while a tool is not configured.")
        return jsonify(Vacuum(0, 0).to_dict())

    return jsonify(Vacuum(globs.state.tool.get_channelA_vacuum(), globs.state.tool.get_channelB_vacuum()).to_dict())


@app.route("/suction/release", methods=["PUT"])
@requires_started
def put_release() -> RespT:
    """Turn off suction.
    ---
    put:
        description: Get the current state.
        tags:
           - Tool
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

    assert globs.state

    if not globs.state.tool:
        logger.warning("PUT /suction/release called while a tool is not configured.")
        return Response(status=204)

    globs.state.tool.release_vacuum()

    return Response(status=204)


def main() -> None:
    parser = argparse.ArgumentParser(description=SERVICE_NAME)
    parser.add_argument("-s", "--swagger", action="store_true", default=False)

    parser.add_argument(
        "-d",
        "--debug",
        help="Set logging level to debug.",
        action="store_const",
        const=logging.DEBUG,
        default=logging.DEBUG if env.get_bool("ARCOR2_UR_DEBUG") else logging.INFO,
    )

    args = parser.parse_args()
    logger.setLevel(args.debug)
    globs.debug = args.debug

    # TODO there will be a ROS-specific scene service
    # if not args.swagger:
    #    scene_service.wait_for()

    if not INTERACT_WITH_DASHBOARD:
        logger.warning("Interaction with robot dashboard disabled. Make sure you know what it means.")

    run_app(
        app,
        SERVICE_NAME,
        version(),
        port_from_url(URL),
        [Vacuum, Pose, Joint, InverseKinematicsRequest, WebApiError],
        args.swagger,
        # dependencies={"ARCOR2 Scene": "1.0.0"},
    )

    if globs.state:
        globs.state.shutdown()


if __name__ == "__main__":
    main()
