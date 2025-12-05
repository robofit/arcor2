import importlib
import multiprocessing
import threading
import time
from multiprocessing.connection import Connection
from typing import Any, Callable, NamedTuple, cast

import rclpy  # pants: no-infer-dep
from geometry_msgs.msg import Pose as RosPose  # pants: no-infer-dep
from geometry_msgs.msg import PoseStamped  # pants: no-infer-dep
from moveit.planning import MoveItPy, PlanningComponent  # pants: no-infer-dep
from moveit_msgs.msg import CollisionObject  # pants: no-infer-dep
from rclpy.callback_groups import MutuallyExclusiveCallbackGroup  # pants: no-infer-dep
from rclpy.node import Node  # pants: no-infer-dep
from rclpy.qos import QoSDurabilityPolicy, QoSProfile, QoSReliabilityPolicy  # pants: no-infer-dep
from sensor_msgs.msg import JointState  # pants: no-infer-dep
from shape_msgs.msg import SolidPrimitive  # pants: no-infer-dep
from std_msgs.msg import Bool, String  # pants: no-infer-dep
from std_srvs.srv import Trigger  # pants: no-infer-dep
from tf2_ros.buffer import Buffer  # pants: no-infer-dep
from tf2_ros.transform_listener import TransformListener  # pants: no-infer-dep
from ur_dashboard_msgs.msg import RobotMode  # pants: no-infer-dep
from ur_dashboard_msgs.srv import Load  # pants: no-infer-dep
from ur_msgs.srv import SetPayload, SetSpeedSliderFraction  # pants: no-infer-dep

from arcor2 import transformations as tr
from arcor2.data import common, object_type
from arcor2.data.common import Joint, Pose
from arcor2.data.robot import InverseKinematicsRequest
from arcor2.logging import get_logger
from arcor2_ur import topics
from arcor2_ur.exceptions import UrGeneral
from arcor2_ur.object_types.ur5e import Vacuum
from arcor2_ur.vgc10 import VGC10

logger = get_logger(__name__)

FREEDRIVE_KEEPALIVE_PERIOD = 0.1


class CollisionObjectTuple(NamedTuple):
    model: object_type.Models
    pose: common.Pose


def pose_to_ros_pose(ps: Pose) -> RosPose:
    rp = RosPose()
    rp.position.x = ps.position.x
    rp.position.y = ps.position.y
    rp.position.z = ps.position.z
    rp.orientation.x = ps.orientation.x
    rp.orientation.y = ps.orientation.y
    rp.orientation.z = ps.orientation.z
    rp.orientation.w = ps.orientation.w
    return rp


def plan_and_execute(
    robot,
    planning_component,
    logger,
    single_plan_parameters=None,
    multi_plan_parameters=None,
    sleep_time=0.0,
) -> None:
    logger.info("Planning trajectory")
    if multi_plan_parameters is not None:
        plan_result = planning_component.plan(multi_plan_parameters=multi_plan_parameters)
    elif single_plan_parameters is not None:
        plan_result = planning_component.plan(single_plan_parameters=single_plan_parameters)
    else:
        plan_result = planning_component.plan()

    if plan_result:
        logger.info("Executing plan")
        robot_trajectory = plan_result.trajectory
        if not robot.execute(robot_trajectory, controllers=[]):
            raise UrGeneral("Trajectory execution failed.")
    else:
        raise UrGeneral("Planning failed")

    time.sleep(sleep_time)


def wait_for_future(future, *, timeout_sec: float = 2.0):
    start = time.monotonic()
    while not future.done() and time.monotonic() - start < timeout_sec:
        time.sleep(0.01)

    if not future.done():
        raise UrGeneral("Service call timed out.")

    return future.result()


class MyNode(Node):
    def __init__(
        self,
        base_link: str,
        tool_link: str,
        interact_with_dashboard: bool = True,
        joint_state_handler: Callable[[list[str], list[float]], None] | None = None,
        debug: bool | int = False,
    ) -> None:
        super().__init__("ur_api_node", enable_logger_service=True)
        if debug:
            rclpy.logging.set_logger_level("ur_api_node", rclpy.logging.LoggingSeverity.DEBUG)

        sub_qos = QoSProfile(
            depth=1, durability=QoSDurabilityPolicy.TRANSIENT_LOCAL, reliability=QoSReliabilityPolicy.RELIABLE
        )

        self.base_link = base_link
        self.tool_link = tool_link
        self.buffer = Buffer()
        self.listener = TransformListener(self.buffer, self)
        self.subscription = self.create_subscription(
            JointState, "joint_states", self.joint_states_cb, 10, callback_group=MutuallyExclusiveCallbackGroup()
        )
        self.interact_with_dashboard = interact_with_dashboard

        self.robot_mode: RobotMode | None = None
        self.robot_program_running: bool | None = None
        self._joint_state_handler = joint_state_handler

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
        self._freedrive_mode = False
        self.freedrive_mode_pub = self.create_publisher(Bool, topics.FREEDRIVE_MODE_TOPIC, 10)
        self.freedrive_timer = self.create_timer(FREEDRIVE_KEEPALIVE_PERIOD, self._freedrive_keepalive)

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
        response = wait_for_future(future)

        if response is None:
            raise UrGeneral("Service call failed!")

        if not response.success:
            raise UrGeneral(f"Service call failed with message: {response.message}")

    def power_off(self) -> None:
        if not self.interact_with_dashboard:
            return

        future = self._power_off_client.call_async(Trigger.Request())
        response = wait_for_future(future)

        if response is None:
            raise UrGeneral("Service call failed!")

        if not response.success:
            raise UrGeneral(f"Service call failed with message: {response.message}")

    def load_program(self) -> None:
        if not self.interact_with_dashboard:
            return

        future = self._load_program_client.call_async(Load.Request(filename="prog.urp"))
        response = wait_for_future(future)

        if response is None:
            raise UrGeneral("Service call failed!")

        if not response.success:
            raise UrGeneral(f"Service call failed with message: {response.answer}")

    def play(self) -> None:
        if not self.interact_with_dashboard:
            return

        future = self._play_client.call_async(Trigger.Request())
        response = wait_for_future(future)

        if response is None:
            raise UrGeneral("Service call failed!")

        if not response.success:
            raise UrGeneral(f"Service call failed with message: {response.message}")

    def set_speed_slider(self, value: float):
        if value <= 0 or value > 1:
            raise UrGeneral("Invalid speed.")

        future = self._set_speed_slider_client.call_async(SetSpeedSliderFraction.Request(speed_slider_fraction=value))
        response = wait_for_future(future)

        if response is None:
            raise UrGeneral("Service call failed!")

        if not response.success:
            raise UrGeneral(f"Service call failed (speed: {value}).")

    def set_payload(self, value: float):
        if value < 0:
            raise UrGeneral("Invalid payload.")

        future = self._set_payload_client.call_async(SetPayload.Request(mass=value))
        response = wait_for_future(future)

        if response is None:
            raise UrGeneral("Service call failed!")

        if not response.success:
            raise UrGeneral("Service call failed.")

    def set_freedrive_mode(self, enabled: bool) -> None:
        self._freedrive_mode = enabled
        self._publish_freedrive_mode(enabled)

    def get_freedrive_mode(self) -> bool:
        return self._freedrive_mode

    def _freedrive_keepalive(self) -> None:
        if not self._freedrive_mode:
            return
        self._publish_freedrive_mode(True)

    def _publish_freedrive_mode(self, enabled: bool) -> None:
        msg = Bool()
        msg.data = enabled
        self.freedrive_mode_pub.publish(msg)

    def joint_states_cb(self, msg: JointState) -> None:
        if self._joint_state_handler is not None:
            self._joint_state_handler(list(msg.name), list(msg.position))


def apply_collision_objects(
    scene, collision_objects: dict[str, CollisionObjectTuple], base_pose: Pose, base_link: str
) -> None:
    scene.remove_all_collision_objects()

    for obj_id, obj in collision_objects.items():
        if not isinstance(obj.model, object_type.Box):
            continue

        collision_object = CollisionObject()
        collision_object.header.frame_id = base_link
        collision_object.id = obj_id

        box_pose = pose_to_ros_pose(tr.make_pose_rel(base_pose, obj.pose))

        box = SolidPrimitive()
        box.type = SolidPrimitive.BOX
        box.dimensions = (obj.model.size_x, obj.model.size_y, obj.model.size_z)

        collision_object.primitives.append(box)
        collision_object.primitive_poses.append(box_pose)
        collision_object.operation = CollisionObject.ADD

        scene.apply_collision_object(collision_object)

    scene.current_state.update()


class RosWorkerRuntime:
    def __init__(
        self,
        base_pose: Pose,
        base_link: str,
        tool_link: str,
        collision_objects: dict[str, CollisionObjectTuple],
        interact_with_dashboard: bool,
        robot_ip: str,
        vgc10_port: int,
        planning_group_name: str,
        moveit_config_dict: dict,
        debug: bool | int,
    ) -> None:
        self.base_pose = base_pose
        self.base_link = base_link
        self.tool_link = tool_link
        self.collision_objects = collision_objects.copy()
        self.joints: list[Joint] = []
        self.tool: VGC10 | None = None
        self.freedrive_mode = False
        self.planning_group_name = planning_group_name
        self.moveitpy: MoveItPy | None = None
        self.ur_manipulator: PlanningComponent | None = None
        self._switch_controller_client: Any = None
        self._list_controllers_client: Any = None

        rclpy.init()
        self.node = MyNode(
            self.base_link,
            self.tool_link,
            interact_with_dashboard,
            joint_state_handler=self._update_joints,
            debug=debug,
        )
        self.executor = rclpy.executors.MultiThreadedExecutor()
        self.executor.add_node(self.node)
        self.executor_thread = threading.Thread(target=self.executor.spin, daemon=True)
        self.executor_thread.start()

        srv_module = importlib.import_module("controller_manager_msgs.srv")
        switch_controller_cls: Any = cast(Any, srv_module.SwitchController)
        list_controllers_cls: Any = cast(Any, srv_module.ListControllers)

        self._switch_controller_client = self.node.create_client(
            switch_controller_cls, "/controller_manager/switch_controller"
        )
        self._list_controllers_client = self.node.create_client(
            list_controllers_cls, "/controller_manager/list_controllers"
        )

        self.node.wait_for_services()
        while not self._switch_controller_client.wait_for_service(timeout_sec=1.0):
            logger.warning("Service /controller_manager/switch_controller not available, waiting again...")
        while not self._list_controllers_client.wait_for_service(timeout_sec=1.0):
            logger.warning("Service /controller_manager/list_controllers not available, waiting again...")

        try:
            self._switch_freedrive_controller(False)
        except Exception:
            logger.exception("Failed to ensure controller state at startup.")

        try:
            self.node.brake_release()
            self.node.load_program()
            self.node.play()
        except Exception:
            self.shutdown()
            raise

        if robot_ip:
            self.tool = VGC10(robot_ip, vgc10_port)
            self.tool.open_connection()

        self.moveitpy = MoveItPy(node_name="moveit_py", config_dict=moveit_config_dict)
        self.ur_manipulator = self.moveitpy.get_planning_component(self.planning_group_name)

        moveitpy, _ = self._get_moveit()
        with moveitpy.get_planning_scene_monitor().read_write() as scene:
            apply_collision_objects(scene, self.collision_objects, self.base_pose, self.base_link)

    def _update_joints(self, names: list[str], positions: list[float]) -> None:
        self.joints = [Joint(name, position) for name, position in zip(names, positions)]

    def shutdown(self) -> None:
        try:
            self._switch_freedrive_controller(False)
        except Exception:
            logger.exception("Failed to switch controllers off during shutdown.")

        try:
            self.node.set_freedrive_mode(False)
        except Exception:
            logger.exception("Failed to clear freedrive mode during shutdown.")
        self.freedrive_mode = False

        try:
            self.node.power_off()
        except Exception:
            logger.exception("Failed to power off robot.")

        if self.tool:
            try:
                self.tool.release_vacuum()
                self.tool.close_connection()
            except Exception:
                logger.exception("Failed to close VGC10 connection.")

        try:
            self.node.destroy_node()
        except Exception:
            logger.exception("Failed to destroy node.")

        try:
            self.executor.shutdown()
        except Exception:
            logger.exception("Failed to shutdown executor.")

        self.executor_thread.join(3)

        try:
            if self.moveitpy:
                self.moveitpy.shutdown()
        except Exception:
            logger.exception("Failed to shutdown moveitpy.")

        try:
            rclpy.shutdown()
        except Exception:
            logger.exception("Failed to shutdown rclpy.")

    def _active_controllers(self) -> set[str]:
        if not self._list_controllers_client:
            return set()
        list_controllers_cls: Any = self._list_controllers_client.srv_type
        req = list_controllers_cls.Request()
        resp = wait_for_future(self._list_controllers_client.call_async(req), timeout_sec=5.0)
        if resp is None:
            return set()
        return {c.name for c in resp.controller if c.state == "active"}

    def _switch_freedrive_controller(self, enable: bool) -> None:
        if not self._switch_controller_client:
            return

        active = self._active_controllers()
        to_activate: list[str] = []
        to_deactivate: list[str] = []

        if enable:
            if "freedrive_mode_controller" not in active:
                to_activate.append("freedrive_mode_controller")
            if "scaled_joint_trajectory_controller" in active:
                to_deactivate.append("scaled_joint_trajectory_controller")
        else:
            if "freedrive_mode_controller" in active:
                to_deactivate.append("freedrive_mode_controller")
            if "scaled_joint_trajectory_controller" not in active:
                to_activate.append("scaled_joint_trajectory_controller")

        if not to_activate and not to_deactivate:
            return

        switch_controller_cls: Any = self._switch_controller_client.srv_type
        req = switch_controller_cls.Request()
        req.activate_controllers = to_activate
        req.deactivate_controllers = to_deactivate
        req.strictness = 2  # STRICT
        req.activate_asap = False
        req.timeout.sec = 5
        req.timeout.nanosec = 0

        resp = wait_for_future(self._switch_controller_client.call_async(req), timeout_sec=10.0)
        if resp is None or not resp.ok:
            msg = getattr(resp, "message", "")
            raise UrGeneral(f"Controller switch failed. {msg}")

    def _current_pose(self) -> Pose:
        ros_time = rclpy.time.Time()

        if not self.node.buffer.can_transform(
            self.base_link, self.tool_link, ros_time, timeout=rclpy.time.Duration(seconds=5.0)
        ):
            raise UrGeneral("Can't get transform")
        transform = self.node.buffer.lookup_transform(self.base_link, self.tool_link, ros_time)

        t = transform.transform

        pose = Pose()
        pose.position.x = t.translation.x
        pose.position.y = t.translation.y
        pose.position.z = t.translation.z

        pose.orientation.x = t.rotation.x
        pose.orientation.y = t.rotation.y
        pose.orientation.z = t.rotation.z
        pose.orientation.w = t.rotation.w

        return tr.make_pose_abs(self.base_pose, pose)

    def get_eef_pose(self) -> dict:
        return self._current_pose().to_dict()

    def _latest_transform_time(self) -> rclpy.time.Time | None:
        try:
            transform = self.node.buffer.lookup_transform(self.base_link, self.tool_link, rclpy.time.Time())
            return rclpy.time.Time.from_msg(transform.header.stamp)
        except Exception:
            return None

    def _wait_for_transform_update(self, since: rclpy.time.Time | None, timeout: float = 2.0) -> None:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            latest = self._latest_transform_time()
            if latest is not None and (since is None or latest > since):
                return
            time.sleep(0.01)
        raise UrGeneral("Transform did not update after motion.")

    def _joints_changed(self, previous: list[Joint]) -> bool:
        if len(previous) != len(self.joints):
            return True
        for prev, current in zip(previous, self.joints):
            if prev.name != current.name:
                return True
            if abs(prev.value - current.value) > 1e-5:
                return True
        return False

    def _wait_for_joint_update(self, previous: list[Joint], timeout: float = 2.0) -> None:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if self._joints_changed(previous):
                return
            time.sleep(0.01)
        raise UrGeneral("Joint states did not update after motion.")

    def _wait_for_pose_reached(self, target: Pose, timeout: float = 15.0, tolerance: float = 0.005) -> None:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            current = self._current_pose()
            if (
                abs(current.position.x - target.position.x) <= tolerance
                and abs(current.position.y - target.position.y) <= tolerance
                and abs(current.position.z - target.position.z) <= tolerance
            ):
                return
            time.sleep(0.02)
        raise UrGeneral("Target pose was not reached.")

    def move_to_pose(self, pose: Pose, velocity: float, payload: float, safe: bool) -> dict:
        if self.freedrive_mode:
            raise UrGeneral("Freedrive mode is active. Disable hand teaching before commanding motion.")

        target_abs = Pose.from_dict(pose.to_dict())
        previous_transform_time = self._latest_transform_time()
        previous_joints = list(self.joints)
        pose = tr.make_pose_rel(self.base_pose, pose)

        pose_goal = PoseStamped()
        pose_goal.header.frame_id = self.base_link

        pose_goal.pose.orientation.x = pose.orientation.x
        pose_goal.pose.orientation.y = pose.orientation.y
        pose_goal.pose.orientation.z = pose.orientation.z
        pose_goal.pose.orientation.w = pose.orientation.w
        pose_goal.pose.position.x = pose.position.x
        pose_goal.pose.position.y = pose.position.y
        pose_goal.pose.position.z = pose.position.z

        moveitpy, ur_manipulator = self._get_moveit()
        with moveitpy.get_planning_scene_monitor().read_write() as scene:
            if safe:
                apply_collision_objects(scene, self.collision_objects, self.base_pose, self.base_link)
            else:
                scene.remove_all_collision_objects()

            scene.current_state.update(force=True)
            scene.current_state.joint_positions = {j.name: j.value for j in self.joints}
            scene.current_state.update()

        ur_manipulator.set_start_state_to_current_state()
        ur_manipulator.set_goal_state(pose_stamped_msg=pose_goal, pose_link=self.tool_link)

        self.node.set_speed_slider(velocity)
        self.node.set_payload(payload)

        plan_and_execute(moveitpy, ur_manipulator, logger)

        # TODO why is this needed (for tests to pass)?
        self._wait_for_joint_update(previous_joints)
        self._wait_for_transform_update(previous_transform_time)
        self._wait_for_pose_reached(target_abs)
        return {}

    def get_joints(self) -> list[dict]:
        return [joint.to_dict() for joint in self.joints]

    def inverse_kinematics(self, ikr: InverseKinematicsRequest) -> list[dict]:
        if not ikr.start_joints:
            ikr.start_joints = self.joints
        elif len(ikr.start_joints) != len(self.joints):
            raise UrGeneral(f"Wrong number of joints! Should be {len(self.joints)}.")

        ikr.pose = tr.make_pose_rel(self.base_pose, ikr.pose)

        moveitpy, _ = self._get_moveit()
        with moveitpy.get_planning_scene_monitor().read_write() as scene:
            if ikr.avoid_collisions:
                apply_collision_objects(scene, self.collision_objects, self.base_pose, self.base_link)
            else:
                scene.remove_all_collision_objects()

            scene.current_state.update(force=True)
            scene.current_state.joint_positions = {j.name: j.value for j in ikr.start_joints}
            pose_goal = pose_to_ros_pose(ikr.pose)

            try:
                if not scene.current_state.set_from_ik(self.planning_group_name, pose_goal, self.tool_link, timeout=3):
                    raise UrGeneral("Can't get IK!")

                scene.current_state.update()

                if (
                    scene.is_state_colliding(
                        robot_state=scene.current_state, joint_model_group_name=self.planning_group_name, verbose=True
                    )
                    and ikr.avoid_collisions
                ):
                    raise UrGeneral("State is in collision.")
            except UrGeneral:
                if not ikr.avoid_collisions:
                    apply_collision_objects(scene, self.collision_objects, self.base_pose, self.base_link)
                raise

            if len(scene.current_state.joint_positions) != len(self.joints):
                raise UrGeneral("Joint count mismatch.")

            return [Joint(jn, jv).to_dict() for jn, jv in scene.current_state.joint_positions.items()]

    def set_freedrive_mode(self, enabled: bool) -> dict:
        self._switch_freedrive_controller(enabled)
        self.node.set_freedrive_mode(enabled)
        self.freedrive_mode = enabled
        return {}

    def get_freedrive_mode(self) -> bool:
        return self.freedrive_mode

    def update_collisions(self, collision_objects: dict[str, CollisionObjectTuple]) -> dict:
        self.collision_objects = collision_objects.copy()
        moveitpy, _ = self._get_moveit()
        with moveitpy.get_planning_scene_monitor().read_write() as scene:
            apply_collision_objects(scene, self.collision_objects, self.base_pose, self.base_link)
        return {}

    def suck(self, vacuum: int) -> dict:
        if not self.tool:
            logger.warning("PUT /suction/suck called while a tool is not configured.")
            return {}
        self.tool.vacuum_on(vacuum)
        return {}

    def release(self) -> dict:
        if not self.tool:
            logger.warning("PUT /suction/release called while a tool is not configured.")
            return {}
        self.tool.release_vacuum()
        return {}

    def vacuum(self) -> dict:
        if not self.tool:
            logger.warning("PUT /suction/vacuum called while a tool is not configured.")
            return Vacuum(0, 0).to_dict()
        return Vacuum(self.tool.get_channelA_vacuum(), self.tool.get_channelB_vacuum()).to_dict()

    def _get_moveit(self) -> tuple[MoveItPy, PlanningComponent]:
        if not self.moveitpy or not self.ur_manipulator:
            raise UrGeneral("MoveIt is not initialized.")
        return self.moveitpy, self.ur_manipulator


def ros_worker_main(
    conn: Connection,
    base_pose: Pose,
    base_link: str,
    tool_link: str,
    collision_objects: dict[str, CollisionObjectTuple],
    interact_with_dashboard: bool,
    robot_ip: str,
    vgc10_port: int,
    planning_group_name: str,
    moveit_config_dict: dict,
    debug: int | bool,
) -> None:
    runtime: RosWorkerRuntime | None = None

    try:
        runtime = RosWorkerRuntime(
            base_pose,
            base_link,
            tool_link,
            collision_objects,
            interact_with_dashboard,
            robot_ip,
            vgc10_port,
            planning_group_name,
            moveit_config_dict,
            debug,
        )
        conn.send({"status": "ok"})
    except Exception as exc:  # pragma: no cover - best effort to report start failure
        logger.exception("Failed to start ROS worker.")
        try:
            conn.send({"status": "error", "message": str(exc)})
        except Exception:
            pass
        return

    try:
        while True:
            try:
                if not conn.poll(0.1):
                    continue
            except (EOFError, BrokenPipeError):
                break

            try:
                msg = conn.recv()
            except (EOFError, BrokenPipeError):
                break

            op = msg.get("op")
            kwargs = msg.get("kwargs", {}) or {}
            result: Any = None

            if op == "shutdown":
                conn.send({"status": "ok"})
                break

            try:
                if op == "get_eef_pose":
                    result = runtime.get_eef_pose()
                elif op == "move_to_pose":
                    pose = Pose.from_dict(kwargs["pose"])
                    result = runtime.move_to_pose(pose, kwargs["velocity"], kwargs["payload"], kwargs["safe"])
                elif op == "get_joints":
                    result = runtime.get_joints()
                elif op == "ik":
                    result = runtime.inverse_kinematics(InverseKinematicsRequest.from_dict(kwargs["ikr"]))
                elif op == "set_freedrive_mode":
                    result = runtime.set_freedrive_mode(bool(kwargs["enabled"]))
                elif op == "get_freedrive_mode":
                    result = runtime.get_freedrive_mode()
                elif op == "update_collisions":
                    result = runtime.update_collisions(kwargs["collision_objects"])
                elif op == "suck":
                    result = runtime.suck(kwargs["vacuum"])
                elif op == "release":
                    result = runtime.release()
                elif op == "vacuum":
                    result = runtime.vacuum()
                else:
                    raise UrGeneral(f"Unknown command {op}")

                conn.send({"status": "ok", "result": result})
            except Exception as exc:
                logger.exception("ROS worker command failed.")
                try:
                    conn.send({"status": "error", "message": str(exc)})
                except Exception:
                    pass
    finally:
        if runtime:
            runtime.shutdown()
        try:
            conn.close()
        except Exception:
            pass


class RosWorkerClient:
    def __init__(
        self,
        pose: Pose,
        collision_objects: dict[str, CollisionObjectTuple],
        base_link: str,
        tool_link: str,
        planning_group_name: str,
        moveit_config_dict: dict,
        interact_with_dashboard: bool,
        robot_ip: str,
        vgc10_port: int,
        debug: bool | int,
    ) -> None:
        ctx = multiprocessing.get_context("spawn")
        self._conn, child_conn = ctx.Pipe()
        self._process = ctx.Process(
            target=ros_worker_main,
            args=(
                child_conn,
                pose,
                base_link,
                tool_link,
                collision_objects,
                interact_with_dashboard,
                robot_ip,
                vgc10_port,
                planning_group_name,
                moveit_config_dict,
                debug,
            ),
            daemon=True,
        )
        self._process.start()
        self._wait_ready()

    def _wait_ready(self) -> None:
        if not self._conn.poll(60):
            raise UrGeneral("ROS worker did not start.")
        resp = self._conn.recv()
        if resp.get("status") != "ok":
            raise UrGeneral(resp.get("message", "Failed to start ROS worker."))

    def request(self, op: str, **kwargs):
        if not self._process.is_alive():
            raise UrGeneral("ROS worker is not running.")
        self._conn.send({"op": op, "kwargs": kwargs})
        if not self._conn.poll(120):
            raise UrGeneral(f"ROS worker did not respond to '{op}'.")
        resp = self._conn.recv()
        if resp.get("status") != "ok":
            raise UrGeneral(resp.get("message", f"ROS worker command '{op}' failed."))
        return resp.get("result")

    def stop(self) -> None:
        if self._process.is_alive():
            try:
                self.request("shutdown")
            except UrGeneral:
                logger.exception("Failed to shut down ROS worker cleanly.")
        self._conn.close()
        self._process.join(timeout=5)
        if self._process.is_alive():
            logger.warning("Forcing ROS worker termination.")
            self._process.kill()
