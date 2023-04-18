import inspect
import os
import signal
import sys
import time
from multiprocessing import Process, Value

from gtts import gTTS
from mouse_controller import MouseFunc, MouseReader
from playsound import playsound

from arcor2.data.common import Flow, LogicItem, Orientation, Parameter, Pose, Position, Project, Scene, StrEnum
from arcor2.data.events import Event
from arcor2.data.rpc import get_id
from arcor2.data.rpc.common import TypeArgs
from arcor2.exceptions import Arcor2Exception
from arcor2_arserver_data import events
from arcor2_arserver_data import rpc as srpc
from arcor2_arserver_data.client import ARServer
from arcor2_arserver_data.events.robot import RobotMoveToData, RobotMoveToPose
from arcor2_arserver_data.objects import ObjectAction
from arcor2_execution_data import EVENTS as EXE_EVENTS


class StateException(Arcor2Exception):
    pass


class MessageFailException(Arcor2Exception):
    pass


class RobotActions:
    def __init__(self, g_name: str, g_desc: str, g_param: list) -> None:
        self.name: str = g_name
        self.desc: str = g_desc
        self.parameters: list = g_param
        for par in self.parameters:
            if par.value is None:
                par.value = "None"


class RobotInfo:
    def __init__(
        self, g_robot_name: str, g_robot_id: str, g_effector_id: str, g_robot_type: str, g_read_effector: bool
    ) -> None:
        self.robot_name: str = g_robot_name
        self.robot_id: str = g_robot_id
        self.effector_id: str = g_effector_id
        self.robot_type: str = g_robot_type
        self.read_effectir: bool = g_read_effector


class ProgramPosition(StrEnum):
    ROBOTMENU = "robotmenu"
    ACTIONMENU = "actionmenu"
    ROBOTMOVEMENT = "robotmovement"


class MouseProgram:
    a_s: ARServer = None
    mouse_func: MouseFunc = None
    program_state = None
    loaded_robots = None
    loaded_actions: list[RobotActions] = None
    current_robot: RobotInfo = None
    current_action: RobotActions = None
    ac_add_counter: int = 0

    def __init__(self, values, connection_string: str = "ws://0.0.0.0:6789") -> None:
        self.init_event_mapping()
        self.a_s = ARServer(ws_connection_str=connection_string, event_mapping=self.event_mapping)
        self.shared = values
        self.mouse_func = MouseFunc()
        self.read_innit_message()
        self.program_state = ProgramPosition.ROBOTMENU

    def init_event_mapping(self):
        self.event_mapping: dict[str, type[Event]] = {evt.__name__: evt for evt in EXE_EVENTS}
        modules = []
        for _, mod in inspect.getmembers(events, inspect.ismodule):
            modules.append(mod)
        for mod in modules:
            for _, cls in inspect.getmembers(mod, inspect.isclass):
                if issubclass(cls, Event):
                    self.event_mapping[cls.__name__] = cls

    def mouse_read(self):
        return self.mouse_func.turn_format(self.shared)

    def get_event(self) -> dict:
        try:
            return self.a_s.get_event()
        except BaseException:
            return None

    def register_user(self, g_name: str) -> srpc.u.RegisterUser.Response:
        return self.a_s.call_rpc(
            srpc.u.RegisterUser.Request(get_id(), srpc.u.RegisterUser.Request.Args(user_name=g_name)),
            srpc.u.RegisterUser.Response,
        )

    def read_text(self, g_text: str) -> None:
        # TODO this version makes temporary save of audio
        language = "en"
        langObj = gTTS(text=g_text, lang=language, slow=False)
        langObj.save("speech.mp3")
        playsound("speech.mp3", True)
        os.remove("speech.mp3")

    def lock_read(self, g_id: str) -> srpc.lock.ReadLock.Response:
        return self.a_s.call_rpc(
            srpc.lock.ReadLock.Request(get_id(), srpc.lock.ReadLock.Request.Args(g_id)), srpc.lock.ReadLock.Response
        )

    def lock_write(self, g_id: str, g_lock_tree: bool = None) -> srpc.lock.WriteLock.Response:
        if g_lock_tree is None:
            return self.a_s.call_rpc(
                srpc.lock.WriteLock.Request(get_id(), srpc.lock.WriteLock.Request.Args(g_id)),
                srpc.lock.WriteLock.Response,
            )
        else:
            return self.a_s.call_rpc(
                srpc.lock.WriteLock.Request(get_id(), srpc.lock.WriteLock.Request.Args(g_id, g_lock_tree)),
                srpc.lock.WriteLock.Response,
            )

    def lock_read_unlock(self, g_id: str) -> srpc.lock.ReadUnlock.Response:
        return self.a_s.call_rpc(
            srpc.lock.ReadUnlock.Request(get_id(), srpc.lock.ReadUnlock.Request.Args(g_id)),
            srpc.lock.ReadUnlock.Response,
        )

    def lock_write_unlock(self, g_id: str) -> srpc.lock.WriteUnlock.Response:
        return self.a_s.call_rpc(
            srpc.lock.WriteUnlock.Request(get_id(), srpc.lock.WriteUnlock.Request.Args(g_id)),
            srpc.lock.WriteUnlock.Response,
        )

    def robot_end_effector_pose(
        self, g_robot_id: str, g_end_effector_id: str, g_arm_id: str = None
    ) -> srpc.r.GetEndEffectorPose.Response:
        if g_arm_id is None:
            return self.a_s.call_rpc(
                srpc.r.GetEndEffectorPose.Request(
                    get_id(), srpc.r.GetEndEffectorPose.Request.Args(g_robot_id, g_end_effector_id)
                ),
                srpc.r.GetEndEffectorPose.Response,
            )
        else:
            return self.a_s.call_rpc(
                srpc.r.GetEndEffectorPose.Request(
                    get_id(), srpc.r.GetEndEffectorPose.Request.Args(g_robot_id, g_end_effector_id, g_arm_id)
                ),
                srpc.r.GetEndEffectorPose.Response,
            )

    def robot_end_effectors_get(self, g_robot_id: str, g_arm_id: str = None) -> srpc.r.GetEndEffectors.Response:
        return self.a_s.call_rpc(
            srpc.r.GetEndEffectors.Request(get_id(), srpc.r.GetEndEffectors.Request.Args(g_robot_id, g_arm_id)),
            srpc.r.GetEndEffectors.Response,
        )

    def robot_arms_get(self, g_robot_id: str) -> srpc.r.GetRobotArms.Response:
        return self.a_s.call_rpc(
            srpc.r.GetRobotArms.Request(get_id(), srpc.r.GetRobotArms.Request.Args(g_robot_id)),
            srpc.r.GetRobotArms.Response,
        )

    def robot_move_to_pose(
        self, g_robot_id: str, g_end_effector_id, g_speed: float, g_position, g_orientation
    ) -> srpc.r.MoveToPose.Response:
        s_data = srpc.r.MoveToPose.Request.Args(g_robot_id, g_end_effector_id, g_speed, g_position, g_orientation)
        return self.a_s.call_rpc(srpc.r.MoveToPose.Request(get_id(), s_data), srpc.r.MoveToPose.Response)

    def robot_meta_get(self) -> srpc.r.GetRobotMeta.Response:
        return self.a_s.call_rpc(srpc.r.GetRobotMeta.Request(get_id()), srpc.r.GetRobotMeta.Response)

    def parse_robot_meta(self) -> list[str]:
        return [robot.type for robot in self.robot_meta_get().data]

    def get_robots_in_scene(self) -> list[RobotInfo]:
        robot_types = self.parse_robot_meta()
        robot_list = []
        for obj in self.cur_scene.objects:
            if obj.type in robot_types:
                effectors = self.robot_end_effectors_get(obj.id)
                for effector in self.robot_end_effectors_get(obj.id):
                    robot_list.append(RobotInfo(obj.name, obj.id, effector, obj.type, len(effectors) > 1))
        return robot_list

    def robot_get_actions(self, g_type: str) -> srpc.o.GetActions.Response:
        return self.a_s.call_rpc(srpc.o.GetActions.Request(get_id(), TypeArgs(g_type)), srpc.o.GetActions.Response)

    def robot_actions_parse(self, g_type: str) -> list:
        meta_data = self.robot_get_actions(g_type).data
        ac_list = []
        for a in meta_data:
            if a.disabled:
                continue
            p_list = self.robot_params_parse(a)
            if p_list is None:
                continue
            ac_list.append(RobotActions(a.name, a.description, p_list))
        return ac_list

    def robot_params_parse(self, g_action: ObjectAction) -> list[Parameter]:
        param_list = []
        for param_meta in g_action.parameters:
            if param_meta.default_value is None and (param_meta.name != "pose" or param_meta.name != "move_type"):
                return None
            if param_meta.default_value is None and param_meta.name == "move_type":
                param_list.append(Parameter(param_meta.name, param_meta.type, '"LINEAR"'))
            else:
                param_list.append(Parameter(param_meta.name, param_meta.type, param_meta.default_value))
        return param_list

    def action_add(self, g_action_point_id: str, g_name: str, g_type: str, g_params: list) -> srpc.p.AddAction.Response:
        return self.a_s.call_rpc(
            srpc.p.AddAction.Request(
                get_id(),
                srpc.p.AddAction.Request.Args(g_action_point_id, g_name, g_type, parameters=g_params, flows=[Flow()]),
            ),
            srpc.p.AddAction.Response,
        )

    def action_point_add_by_robot(self, g_robot_id: str, g_end_effector_id: str, g_name: str) -> srpc.p.AddApUsingRobot:
        return self.a_s.call_rpc(
            srpc.p.AddApUsingRobot.Request(
                get_id(), srpc.p.AddApUsingRobot.Request.Args(g_robot_id, g_end_effector_id, g_name)
            ),
            srpc.p.AddApUsingRobot.Response,
        )

    def logic_add(self, g_start, g_end) -> srpc.p.AddLogicItem.Response:
        return self.a_s.call_rpc(
            srpc.p.AddLogicItem.Request(get_id(), srpc.p.AddLogicItem.Request.Args(g_start, g_end)),
            srpc.p.AddLogicItem.Response,
        )

    def logic_update(self, g_id, g_start, g_end) -> srpc.p.UpdateLogicItem.Response:
        return self.a_s.call_rpc(
            srpc.p.UpdateLogicItem.Request(get_id(), srpc.p.UpdateLogicItem.Request.Args(g_id, g_start, g_end)),
            srpc.p.UpdateLogicItem.Response,
        )

    def find_last_logic(self, logiclist: list[LogicItem]) -> LogicItem:
        start = None
        for li in logiclist:
            if li.start == "START":
                start = li
                break
        if start is None:
            return start
        current = start
        while 1:
            if current.end == "END":
                return current
            next = None
            for li in logiclist:
                if li.start == current.end:
                    next = li
                    break
            if next is None:
                return current
            current = next

    def update_logic(self, logiclist: list[LogicItem], new_action: str) -> None:
        last = self.find_last_logic(logiclist)
        if last is None:
            self.logic_add("START", new_action)
            self.logic_add(new_action, "END")
        else:
            self.logic_update(last.id, last.start, new_action)
            self.logic_add(new_action, "END")

    def read_innit_message(self) -> None:
        received_event = self.get_event()
        if received_event is None:
            raise MessageFailException("Init messages were not recieved.")
        if not isinstance(received_event, events.project.OpenProject):
            raise StateException("Server is not in project editing state.")
        self.cur_proj: Project = received_event.data.project
        self.cur_scene: Scene = received_event.data.scene
        received_event_2 = self.get_event()
        if received_event_2 is None:
            raise MessageFailException("Init message 2 was not recieved.")
        if not isinstance(received_event_2, events.scene.SceneState):
            raise StateException("Server is not in project editing state.")
        self.scene_state = received_event_2.data.state

    def get_mov_pos(self, g_robot_id: str, g_end_effector_id: str, g_mouse_reading, g_arm_id: str = None):
        g_sensitivity = 0.015
        def_pos = self.robot_end_effector_pose(g_robot_id, g_end_effector_id, g_arm_id)
        if not def_pos.response:
            raise MessageFailException("Failed to get robot effector position")
        def_pos = def_pos.data
        def_pos.position.x = def_pos.position.x + g_mouse_reading.x * g_sensitivity
        def_pos.position.y = def_pos.position.y + g_mouse_reading.y * g_sensitivity
        def_pos.position.z = def_pos.position.z + g_mouse_reading.z * g_sensitivity

        def_pos.orientation.__mul__(
            Orientation().from_rotation_vector(
                g_mouse_reading.roll * g_sensitivity,
                g_mouse_reading.pitch * g_sensitivity,
                g_mouse_reading.yaw * g_sensitivity,
            )
        )
        return def_pos

    def register_for_robot_event(self, g_robot_id: str) -> srpc.r.RegisterForRobotEvent.Response:
        enum = srpc.r.RegisterForRobotEvent.Request.Args.RegisterEnum.EEF_POSE
        return self.a_s.call_rpc(
            srpc.r.RegisterForRobotEvent.Request(
                get_id(), srpc.r.RegisterForRobotEvent.Request.Args(g_robot_id, enum, True)
            ),
            srpc.r.RegisterForRobotEvent.Response,
        )

    def highligth_robot_mechanic(self, g_robot_id: str, g_end_effector_id: str, g_arm_id: str = None) -> None:
        # TODO redefine offset base on testing#TODO unregister
        self.register_for_robot_event(g_robot_id)
        # Pose
        def_pos = self.robot_end_effector_pose(g_robot_id, g_end_effector_id, g_arm_id).data
        pos_offset = 0.01
        # rot_offset = 5

        # pose 1
        pos1 = Pose()
        pos1.position = Position(
            def_pos.position.x - pos_offset, def_pos.position.y - pos_offset, def_pos.position.z + pos_offset / 2
        )
        pos1.orientation = def_pos.orientation

        # pose 2
        pos2 = Pose()
        pos2.position = Position(def_pos.position.x, def_pos.position.y, def_pos.position.z + pos_offset)
        pos2.orientation = def_pos.orientation

        # pose 3
        pos3 = Pose()
        pos3.position = Position(
            def_pos.position.x + pos_offset, def_pos.position.y + pos_offset, def_pos.position.z + pos_offset / 2
        )
        pos3.orientation = def_pos.orientation

        self.robot_move_to_pose(g_robot_id, g_end_effector_id, 0.5, pos1.position, pos1.orientation)
        self.wait_for_movement()

        self.robot_move_to_pose(g_robot_id, g_end_effector_id, 0.5, pos2.position, pos2.orientation)
        self.wait_for_movement()

        self.robot_move_to_pose(g_robot_id, g_end_effector_id, 0.5, pos3.position, pos3.orientation)
        self.wait_for_movement()

        self.robot_move_to_pose(g_robot_id, g_end_effector_id, 0.5, def_pos.position, def_pos.orientation)
        self.wait_for_movement()

    # Program brain
    def robot_layer_innit(self) -> None:
        self.loaded_robots = self.get_robots_in_scene()

    def action_layer_innit(self) -> None:
        self.loaded_actions = self.robot_actions_parse(self.current_robot.robot_type)

    def program_loop(self) -> None:
        self.robot_layer_innit()
        while 1:
            if self.program_state == ProgramPosition.ROBOTMENU:
                self.robot_layer_loop()
            if self.program_state == ProgramPosition.ACTIONMENU:
                self.action_layer_loop()
            if self.program_state == ProgramPosition.ROBOTMOVEMENT:
                self.robot_movement_loop()

    def robot_layer_loop(self) -> None:
        index = 0
        self.read_text(self.loaded_robots[index].robot_name)
        exit_flag: bool = False
        while 1:
            reading = self.mouse_read()
            if self.mouse_func.mouse_button_left_pressed(reading):
                self.read_text("chosen" + self.loaded_robots[index].robot_name)
                self.current_robot = self.loaded_robots[index]
                self.program_state = ProgramPosition.ACTIONMENU
                return
            if self.mouse_func.mouse_button_rigth_pressed(reading) and exit_flag:
                sys.exit(0)
            if self.mouse_func.mouse_button_rigth_pressed(reading):
                self.read_text("Exit?")
                exit_flag = True
            if self.mouse_func.menu_left_movement(reading):
                index -= 1
                index = self.clamp_index(index, 0, self.loaded_robots.__len__() - 1)
                self.read_text(self.loaded_robots[index].robot_name)
                exit_flag = False
            if self.mouse_func.menu_rigth_movement(reading):
                index += 1
                index = self.clamp_index(index, 0, self.loaded_robots.__len__() - 1)
                self.read_text(self.loaded_robots[index].robot_name)
                exit_flag = False

    def action_layer_loop(self) -> None:
        # TODO M1 dobot crashed here for sum reason
        index = 0
        self.action_layer_innit()
        self.read_text(self.loaded_actions[index].name)
        exit_flag: bool = False
        while 1:
            reading = self.mouse_read()
            if self.mouse_func.mouse_button_left_pressed(reading):
                self.read_text("chosen" + self.loaded_actions[index].name)
                self.current_action = self.loaded_actions[index]
                self.program_state = ProgramPosition.ROBOTMOVEMENT
            if self.mouse_func.mouse_button_rigth_pressed(reading) and exit_flag:
                self.current_robot = None
                self.program_state = ProgramPosition.ROBOTMENU
                self.loaded_actions = None
                return
            if self.mouse_func.mouse_button_rigth_pressed(reading):
                self.read_text("Cancel?")
                exit_flag = True
            if self.mouse_func.menu_left_movement(reading):
                index -= 1
                index = self.clamp_index(index, 0, self.loaded_actions.__len__() - 1)
                self.read_text(self.loaded_actions[index].name)
                exit_flag = False
            if self.mouse_func.menu_rigth_movement(reading):
                index += 1
                index = self.clamp_index(index, 0, self.loaded_actions.__len__() - 1)
                self.read_text(self.loaded_actions[index].name)
                exit_flag = False
            if self.mouse_func.menu_top_movement(reading):
                self.read_text(self.loaded_actions[index].desc)
                exit_flag = False

    def robot_movement_loop(self) -> None:
        robot_id: str = self.current_robot.robot_id
        effector_id: str = self.current_robot.effector_id
        exit_flag: bool = False
        self.register_for_robot_event(robot_id)
        while True:
            reading = self.mouse_read()
            if self.treshold_check(reading.x, reading.y, reading.z, 0.1):
                pose = self.get_mov_pos(robot_id, effector_id, reading)
                self.robot_move_to_pose(robot_id, effector_id, 0.5, pose.position, pose.orientation)
                self.wait_for_movement()
                exit_flag = False
            if self.mouse_func.mouse_button_left_pressed(reading):
                self.finish_action()
                self.current_action = None
                self.current_robot = None
                self.program_state = ProgramPosition.ROBOTMENU
                return
            if self.mouse_func.mouse_button_rigth_pressed(reading) and exit_flag:
                self.program_state = ProgramPosition.ACTIONMENU
                self.current_action = None
                return
            if self.mouse_func.mouse_button_rigth_pressed(reading):
                self.read_text("Cancel?")
                exit_flag = True

    def finish_action(self):
        # TODO not finished
        robot_id = self.current_robot.robot_id
        eff_id = self.current_robot.effector_id
        action_name = self.current_action.name
        point_name = str(self.ac_add_counter) + "_" + robot_id + "_" + eff_id + "_" + action_name
        orinetation_id = None
        print(self.action_point_add_by_robot(robot_id, eff_id, point_name))
        for param in self.current_action.parameters:
            if param.name == "pose":
                param.value = orinetation_id

    def clamp_index(self, number: float, l_clamp: float, r_clamp: float) -> float:
        if number < l_clamp:
            return r_clamp
        if number > r_clamp:
            return l_clamp
        return number

    def edit_string(self, string: str) -> str:
        return '"' + string + '"'

    def mabs(self, x):
        return x if x > 0 else -x

    def treshold_check(self, x: float, y: float, z: float, treshold: float) -> bool:
        return self.mabs(x) > treshold or self.mabs(y) > treshold or self.mabs(z) > treshold

    def wait_for_movement(self):
        while 1:
            event = self.get_event()
            if event is None:
                raise MessageFailException("No event recieved from server.")
            if type(event) == RobotMoveToPose:
                if (
                    event.data.move_event_type == RobotMoveToData.MoveEventType.END
                    or event.data.move_event_type == RobotMoveToData.MoveEventType.FAILED
                ):
                    break


def f(x, y, z, roll, pitch, yaw, lmb, rmb):
    mouse = MouseReader()
    time.sleep(1)

    while True:
        time.sleep(0.01)
        v = mouse.mouse_read()
        x.value = v.x
        y.value = v.y
        z.value = v.z
        roll.value = v.roll
        pitch.value = v.pitch
        yaw.value = v.yaw
        lmb.value = v.buttons[0]
        rmb.value = v.buttons[1]


def exit_gracefully(*args):
    sys.exit(0)


def prepare_process():
    x = Value("f", 0.0)
    y = Value("f", 0.0)
    z = Value("f", 0.0)
    roll = Value("f", 0.0)
    pitch = Value("f", 0.0)
    yaw = Value("f", 0.0)
    lmb = Value("i", 0)
    rmb = Value("i", 0)
    p = Process(
        target=f,
        args=(
            x,
            y,
            z,
            roll,
            pitch,
            yaw,
            lmb,
            rmb,
        ),
    )
    return p, [x, y, z, roll, pitch, yaw, lmb, rmb]


signal.signal(signal.SIGINT, exit_gracefully)
signal.signal(signal.SIGTERM, exit_gracefully)
p, values = prepare_process()
try:
    p.start()
    mouse = MouseProgram(values, connection_string="ws://0.0.0.0:6789")
    mouse.register_user("Namae")
    # Error Robot movement failed with: arcor2_dobot (DobotGeneral): Alarm(s): PLAN_INV_LIMIT.
    # mouse.highligth_robot_mechanic("obj_5143000ceec44766b0dda64e422481ab","default")
except BaseException:
    p.join()
