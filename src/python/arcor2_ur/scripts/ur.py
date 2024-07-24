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
from rclpy.node import Node  # pants: no-infer-dep
from sensor_msgs.msg import JointState  # pants: no-infer-dep
from std_srvs.srv import Trigger  # pants: no-infer-dep
from tf2_geometry_msgs import do_transform_pose  # pants: no-infer-dep
from tf2_ros.buffer import Buffer  # pants: no-infer-dep
from tf2_ros.transform_listener import TransformListener  # pants: no-infer-dep
from ur_dashboard_msgs.srv import Load  # pants: no-infer-dep

from arcor2 import env
from arcor2 import transformations as tr
from arcor2.data.common import Joint, Pose
from arcor2.data.robot import InverseKinematicsRequest
from arcor2.flask import RespT, create_app, run_app
from arcor2.helpers import port_from_url
from arcor2.logging import get_logger
from arcor2_ur import get_data, version
from arcor2_ur.exceptions import StartError, UrGeneral, WebApiError

logger = get_logger(__name__)

URL = os.getenv("ARCOR2_UR_URL", "http://localhost:5012")
BASE_LINK = os.getenv("ARCOR2_UR_BASE_LINK", "base_link")
TOOL_LINK = os.getenv("ARCOR2_UR_TOOL_LINK", "tool0")
UR_TYPE = os.getenv("ARCOR2_UR_TYPE", "ur5e")
PLANNING_GROUP_NAME = os.getenv("ARCOR2_UR_PLANNING_GROUP_NAME", "ur_manipulator")

SERVICE_NAME = f"UR Web API ({UR_TYPE})"

INTERACT_WITH_DASHBOARD = env.get_bool("ARCOR2_UR_INTERACT_WITH_DASHBOARD", True)

BRAKE_RELEASE_SRV = "/dashboard_client/brake_release"
POWER_OFF_SRV = "/dashboard_client/power_off"
LOAD_PROGRAM_SRV = "/dashboard_client/load_program"
PLAY_SRV = "/dashboard_client/play"


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
        super().__init__("my_node")

        self.buffer = Buffer()
        self.listener = TransformListener(self.buffer, self)
        self.subscription = self.create_subscription(JointState, "joint_states", self.listener_callback, 10)
        self.interact_with_dashboard = interact_with_dashboard

        self._break_release_client = self.create_client(Trigger, BRAKE_RELEASE_SRV)
        while self.interact_with_dashboard and not self._break_release_client.wait_for_service(timeout_sec=1.0):
            logger.warning(f"Service {BRAKE_RELEASE_SRV} not available, waiting again...")

        self._power_off_client = self.create_client(Trigger, POWER_OFF_SRV)
        while self.interact_with_dashboard and not self._power_off_client.wait_for_service(timeout_sec=1.0):
            logger.warning(f"Service {POWER_OFF_SRV} not available, waiting again...")

        self._load_program_client = self.create_client(Load, LOAD_PROGRAM_SRV)
        while self.interact_with_dashboard and not self._load_program_client.wait_for_service(timeout_sec=1.0):
            logger.warning(f"Service {LOAD_PROGRAM_SRV} not available, waiting again...")

        self._play_client = self.create_client(Trigger, PLAY_SRV)
        while self.interact_with_dashboard and not self._play_client.wait_for_service(timeout_sec=1.0):
            logger.warning(f"Service {PLAY_SRV} not available, waiting again...")

    def brake_release(self) -> None:
        if not self.interact_with_dashboard:
            return

        future = self._break_release_client.call_async(Trigger.Request())
        rclpy.spin_until_future_complete(self, future, timeout_sec=2)

        if future.result() is None:
            raise Exception("Service call failed!")

        response = future.result()
        if not response.success:
            raise Exception(f"Service call failed with message: {response.message}")

    def power_off(self) -> None:
        if not self.interact_with_dashboard:
            return

        future = self._power_off_client.call_async(Trigger.Request())
        rclpy.spin_until_future_complete(self, future, timeout_sec=2)

        if future.result() is None:
            raise Exception("Service call failed!")

        response = future.result()
        if not response.success:
            raise Exception(f"Service call failed with message: {response.message}")

    def load_program(self) -> None:
        if not self.interact_with_dashboard:
            return

        future = self._load_program_client.call_async(Load.Request(filename="prog.urp"))
        rclpy.spin_until_future_complete(self, future, timeout_sec=2)

        if future.result() is None:
            raise Exception("Service call failed!")

        response = future.result()
        if not response.success:
            raise Exception(f"Service call failed with message: {response.answer}")

    def play(self) -> None:
        if not self.interact_with_dashboard:
            return

        future = self._play_client.call_async(Trigger.Request())
        rclpy.spin_until_future_complete(self, future, timeout_sec=2)

        if future.result() is None:
            raise Exception("Service call failed!")

        response = future.result()
        if not response.success:
            raise Exception(f"Service call failed with message: {response.message}")

    def listener_callback(self, msg: JointState) -> None:
        joints = []
        for name, position in zip(msg.name, msg.position):
            joints.append(Joint(name, position))
        if globs.state is not None:
            globs.state.joints = joints  # TODO not very clean solution


@dataclass
class State:
    pose: Pose
    node: MyNode
    moveitpy: MoveItPy
    ur_manipulator: PlanningComponent
    joints: list[Joint] = field(default_factory=list)

    _executor: rclpy.executors.MultiThreadedExecutor | None = None
    _executor_thread: threading.Thread | None = None

    def shutdown(self) -> None:
        assert self._executor
        assert self._executor_thread

        self.node.destroy_node()
        self._executor.shutdown()
        self._executor_thread.join(3)
        assert not self._executor_thread.is_alive()
        self.moveitpy.shutdown()
        rclpy.shutdown()

    def __post_init__(self) -> None:
        self._executor = rclpy.executors.MultiThreadedExecutor()
        self._executor.add_node(self.node)
        self._executor_thread = threading.Thread(target=self._executor.spin, daemon=True)
        self._executor_thread.start()


@dataclass
class Globs:
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

    # TODO find better way how to detect that the launch was started (wait for some topic?)
    time.sleep(2)

    node = MyNode(INTERACT_WITH_DASHBOARD)
    try:
        node.brake_release()
        node.load_program()
        node.play()
    except Exception:
        node.destroy_node()
        rclpy.shutdown()
        raise

    moveitpy = MoveItPy(node_name="moveit_py", config_dict=moveit_config)
    globs.state = State(pose, node, moveitpy, moveitpy.get_planning_component(PLANNING_GROUP_NAME))

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

    plan_and_execute(globs.state.moveitpy, globs.state.ur_manipulator, logger, sleep_time=3.0)

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
        [Pose, Joint, InverseKinematicsRequest, WebApiError],
        args.swagger,
        # dependencies={"ARCOR2 Scene": "1.0.0"},
    )

    if globs.state:
        globs.state.shutdown()


if __name__ == "__main__":
    main()
