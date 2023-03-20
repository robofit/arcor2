import os

# from arcor2_arserver_data.client import ARServer
from ARServer import ARServer
from gtts import gTTS
from MouseClass import MouseClass
from playsound import playsound
# from arcor2_arserver_data import client
# from ServerController import TestServerController

from arcor2.data.common import Orientation, Pose, Position, StrEnum
# from arcor2.data.common import LogicItem
from arcor2.data.rpc import get_id
from arcor2.data.rpc.common import RPC, TypeArgs
# from arcor2.data.rpc.common import IdArgs
# from arcor2.data.rpc.common import RobotArg
from arcor2_arserver_data import rpc as srpc

# import time
# from typing import TypeVar


class StateException(Exception):
    pass


class RobotActions:
    def __init__(self, g_name: str, g_desc: str, g_speed: str) -> None:
        self.name: str = g_name
        self.desc: str = g_desc
        self.speed: float = g_speed

    def __repr__(self) -> str:
        if self.speed is None:
            sppe = "0"
        else:
            sppe = self.speed
        return self.name + " " + sppe


class RobotInfo:
    def __init__(self, g_robot_name: str, g_robot_id: str, g_effector_id: str, g_robot_type: str) -> None:
        self.robot_name: str = g_robot_name
        self.robot_id: str = g_robot_id
        self.effector_id: str = g_effector_id
        self.robot_type: str = g_robot_type


class ProgramPosiotion(StrEnum):
    ROBOTMENU = "robotmenu"
    ACTIONMENU = "actionmenu"
    ROBOTMOVEMENT = "robotmovement"


class MouseProgram:
    a_s: ARServer = None
    mouse: MouseClass = None
    program_state = None
    loaded_robots = None
    loaded_actions = None
    current_robot: RobotInfo = None
    current_action: str = None

    # TODO exceptions here
    def __init__(self, connection_string: str = "ws://0.0.0.0:6789") -> None:
        self.a_s = ARServer(ws_connection_str=connection_string)
        self.mouse = MouseClass()
        self.read_innit_message()
        self.program_state = ProgramPosiotion.ROBOTMENU

    def get_event(self) -> dict:
        try:
            return self.a_s.get_event()
        except Exception:
            return "no event"

    def register_user(self, g_name: str) -> RPC.Response:
        return print(
            self.a_s.call_rpc(
                srpc.u.RegisterUser.Request(get_id(), srpc.u.RegisterUser.Request.Args(user_name=g_name)),
                srpc.u.RegisterUser.Response,
            )
        )

    # Yeller
    # TODO this version makes temporary save of audio
    def read_text(self, g_text: str) -> None:
        language = "en"
        langObj = gTTS(text=g_text, lang=language, slow=False)
        langObj.save("speech.mp3")
        playsound("speech.mp3", True)
        os.remove("speech.mp3")

    # Locker
    # ? Je nutne updatovat lock ?Otestovat fail locku

    # UT
    def lock_read(self, g_id: str) -> RPC.Response:
        return self.a_s.call_rpc(
            srpc.lock.ReadLock.Request(get_id(), srpc.lock.ReadLock.Request.Args(g_id)), srpc.lock.ReadLock.Response
        )

    # UT
    def lock_write(self, g_id: str, g_lock_tree: bool = None) -> RPC.Response:
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

    # UT
    def lock_read_unlock(self, g_id: str) -> RPC.Response:
        return self.a_s.call_rpc(
            srpc.lock.ReadUnlock.Request(get_id(), srpc.lock.ReadUnlock.Request.Args(g_id)),
            srpc.lock.ReadUnlock.Response,
        )

    # UT
    def lock_write_unlock(self, g_id: str) -> RPC.Response:
        return self.a_s.call_rpc(
            srpc.lock.WriteUnlock.Request(get_id(), srpc.lock.WriteUnlock.Request.Args(g_id)),
            srpc.lock.WriteUnlock.Response,
        )

    # Robot Mover

    def robot_end_effector_pose(self, g_robot_id: str, g_end_effector_id: str, g_arm_id: str = None) -> RPC.Response:
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

    def robot_end_effectors_get(self, g_robot_id: str, g_arm_id: str = None) -> RPC.Response:
        return self.a_s.call_rpc(
            srpc.r.GetEndEffectors.Request(get_id(), srpc.r.GetEndEffectors.Request.Args(g_robot_id, g_arm_id)),
            srpc.r.GetEndEffectors.Response,
        ).data

    def robot_arms_get(self, g_robot_id: str) -> RPC.Response:
        return self.a_s.call_rpc(
            srpc.r.GetRobotArms.Request(get_id(), srpc.r.GetRobotArms.Request.Args(g_robot_id)),
            srpc.r.GetRobotArms.Response,
        )

    # UT ?linear ?Move to action point vypada rovnako
    def robot_move_to_pose(
        self, g_robot_id: str, g_end_effector_id, g_speed: float, g_position, g_orientation, g_arm_id: str = None
    ) -> RPC.Response:
        if g_arm_id is None:
            s_data = srpc.r.MoveToPose.Request.Args(g_robot_id, g_end_effector_id, g_speed, g_position, g_orientation)
        else:
            s_data = srpc.r.MoveToPose.Request.Args(
                g_robot_id, g_end_effector_id, g_speed, g_position, g_orientation, g_arm_id
            )
        return self.a_s.call_rpc(srpc.r.MoveToPose.Request(get_id(), s_data), srpc.r.MoveToPose.Response)

    # Robots layer

    def robot_meta_get(self) -> RPC.Response:
        return self.a_s.call_rpc(srpc.r.GetRobotMeta.Request(get_id()), srpc.r.GetRobotMeta.Response)

    def parse_robot_meta(self) -> list:
        robot_list = []
        for robot in self.robot_meta_get():
            robot_list.append(robot.data.type)
        return robot_list

    def get_robots_in_scene(self) -> list[RobotInfo]:
        robot_types = self.parse_robot_meta()
        robot_list = []
        for obj in self.cur_scene["objects"]:
            if obj["type"] in robot_types:
                for effector in self.robot_end_effectors_get(obj["id"]):
                    robot_list.append(RobotInfo(obj["name"], obj["id"], effector, obj["type"]))
        return robot_list

    # Robot actions layer

    def robot_get_actions(self, g_type: str) -> RPC.Response:
        return self.a_s.call_rpc(srpc.o.GetActions.Request(get_id(), TypeArgs(g_type)), srpc.o.GetActions.Response)

    def robot_actions_parse(self, g_type: str) -> list:
        meta_data = self.robot_get_actions(g_type).data
        ac_list = []
        for a in meta_data:
            speed = None
            for p in a.parameters:
                if p.name == "velocity":
                    speed = p.default_value
                    break
            ac_list.append(RobotActions(a.name, a.description, speed))
        return ac_list

    # Actions
    def action_point_add(self, g_name: str, g_position) -> RPC.Response:
        return self.a_s.call_rpc(
            srpc.p.AddActionPoint.Request(get_id(), srpc.p.AddActionPoint.Request.Args(g_name, g_position)),
            srpc.p.AddActionPoint.Response,
        )

    # NW Flow error
    def action_add(self, g_action_point_id: str, g_name: str, g_type: str) -> RPC.Response:
        return self.a_s.call_rpc(
            srpc.p.AddAction.Request(get_id(), srpc.p.AddAction.Request.Args(g_action_point_id, g_name, g_type)),
            srpc.p.AddAction.Response,
        )

    # UT
    def logic_add(self, g_start, g_end) -> RPC.Response:
        return self.a_s.call_rpc(
            srpc.p.AddLogicItem.Request(get_id(), srpc.p.AddLogicItem.Request.Args(g_start, g_end)),
            srpc.p.AddLogicItem.Response,
        )

    # Special functions

    def read_innit_message(self) -> None:
        received_event = self.get_event()
        if not received_event["event"][0] == "OpenProject":
            raise StateException("Server is not in project editing state.")
        self.cur_proj = received_event["data"]["project"]
        self.cur_scene = received_event["data"]["scene"]

        # TODO For now just empties
        self.get_event()
        # print(scene_state)

    # Tu mozno treba inu senzitivitu na rotation a inu na position
    # Okrem toho sem mozno treba dodat tu minimalnu barieru nech to necita nahodne udaje
    def move_robot_with_mouse(
        self,
        g_robot_id: str,
        g_end_effector_id: str,
        g_mouse_reading,
        g_sensitivity: float,
        g_speed: float,
        g_arm_id: str = None,
    ) -> RPC.Response:
        def_pos = self.robot_end_effector_pose(g_robot_id, g_end_effector_id, g_arm_id)
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
        return self.robot_move_to_pose(
            g_robot_id, g_end_effector_id, g_speed, def_pos.position, def_pos.orientation, g_arm_id
        )

    # NT
    # TODO redefine offset base on testing, add waits, if needed
    def highligth_robot_mechanic(
        self, g_robot_id: str, g_end_effector_id: str, g_speed: float, g_arm_id: str = None
    ) -> None:
        # Pose
        def_pos = self.robot_end_effector_pose(g_robot_id, g_end_effector_id, g_arm_id)
        pos_offset = 0.01
        rot_offset = 15

        # pose 1
        pos1 = Pose()
        pos1.position = Position(def_pos.position.x, def_pos.position.y - pos_offset, def_pos.position.z - pos_offset)
        pos1.orientation = Orientation().from_rotation_vector(0, 0, 0)

        # pose 2
        pos2 = Pose()
        pos2.position = Position(def_pos.position.x - pos_offset, def_pos.position.y, def_pos.position.z)
        pos2.orientation = Orientation().from_rotation_vector(-rot_offset, -rot_offset, -rot_offset)

        # pose 3
        pos3 = Pose()
        pos3.position = Position(def_pos.position.x, def_pos.position.y + pos_offset, def_pos.position.z + pos_offset)
        pos3.orientation = Orientation().from_rotation_vector(0, 0, 0)

        # pose 4
        pos4 = Pose()
        pos4.position = Position(def_pos.position.x + pos_offset, def_pos.position.y, def_pos.position.z)
        pos4.orientation = Orientation().from_rotation_vector(rot_offset, rot_offset, rot_offset)

        self.robot_move_to_pose(g_robot_id, g_end_effector_id, g_speed, pos1.position, pos1.orientation, g_arm_id)
        self.robot_move_to_pose(g_robot_id, g_end_effector_id, g_speed, pos2.position, pos2.orientation, g_arm_id)
        self.robot_move_to_pose(g_robot_id, g_end_effector_id, g_speed, pos3.position, pos3.orientation, g_arm_id)
        self.robot_move_to_pose(g_robot_id, g_end_effector_id, g_speed, pos4.position, pos4.orientation, g_arm_id)
        self.robot_move_to_pose(g_robot_id, g_end_effector_id, g_speed, def_pos.position, def_pos.orientation, g_arm_id)

    # Helper
    def clamp_index(self, number: float, l_clamp: float, r_clamp: float) -> float:
        if number < l_clamp:
            return r_clamp
        if number > r_clamp:
            return l_clamp
        return number

    # Program brain
    def robot_layer_innit(self) -> None:
        self.loaded_robots = self.get_robots_in_scene()

    def action_layer_innit(self) -> None:
        self.loaded_actions = self.robot_get_actions(self.current_robot.robot_type)

    def program_loop(self) -> None:
        self.robot_layer_innit()
        while 1:
            if self.program_state == ProgramPosiotion.ROBOTMENU:
                self.robot_layer_loop()
            if self.program_state == ProgramPosiotion.ACTIONMENU:
                self.action_layer_loop()

    def robot_layer_loop(self) -> None:
        index = 0
        self.read_text(self.loaded_robots[index].robot_name)
        while 1:
            reading = self.mouse.mouse_read()
            if self.mouse.mouse_button_left_pressed(reading):
                self.read_text("chosen" + self.loaded_robots[index].robot_name)
                self.current_robot = self.loaded_robots[index]
                self.program_state = ProgramPosiotion.ACTIONMENU
                return
            if self.mouse.menu_left_movement(reading):
                index -= 1
                index = self.clamp_index(index, 0, self.loaded_robots.__len__() - 1)
                self.read_text(self.loaded_robots[index].robot_name)
            if self.mouse.menu_rigth_movement(reading):
                index += 1
                index = self.clamp_index(index, 0, self.loaded_robots.__len__() - 1)
                self.read_text(self.loaded_robots[index].robot_name)

    # TODO SEm pojdu highlith robot commandy

    # TODO na tom M1 tu daco padlo
    def action_layer_loop(self) -> None:
        index = 0
        self.action_layer_innit()
        self.read_text(self.loaded_actions[index].name)
        while 1:
            reading = self.mouse.mouse_read()
            if self.mouse.mouse_button_left_pressed(reading):
                self.read_text("chosen" + self.loaded_actions[index].name)
            if self.mouse.mouse_button_rigth_pressed(reading):
                # TODO double cancel by bolo mozno vhodne
                self.current_robot = None
                self.program_state = ProgramPosiotion.ROBOTMENU
                self.loaded_actions = None
                return
            if self.mouse.menu_left_movement(reading):
                index -= 1
                index = self.clamp_index(index, 0, self.loaded_actions.__len__() - 1)
                self.read_text(self.loaded_actions[index].name)
            if self.mouse.menu_rigth_movement(reading):
                index += 1
                index = self.clamp_index(index, 0, self.loaded_actions.__len__() - 1)
                self.read_text(self.loaded_actions[index].name)
            if self.mouse.menu_top_movement(reading):
                self.read_text(self.loaded_actions[index].description)


mouse = MouseProgram()
# print(mouse.cur_proj)
# print(mouse.cur_scene)

# print(mouse.register_user("Namae"))

# typ napr = obj_5143000ceec44766b0dda64e422481ab/move
# flow not found error
# print(mouse.action_add("acp_783b448e55e446d28210c8aab4752f93","ac1_move","obj_5143000ceec44766b0dda64e422481ab/move"))

# print(mouse.logic_add("START/default","END/default"))


# mouse.action_point_add("ac_1",Position(0,0,0))

# print(mouse.get_event())
# current = mouse.robot_end_effector_pose("obj_4162a203c72f40eea72b3ee1151920c6","default")
# print(mouse.lock_write("obj_4162a203c72f40eea72b3ee1151920c6"))
# print(current)
# current.position.z += 0.05
# print(current)
# print(mouse.robot_move_to_pose("obj_4162a203c72f40eea72b3ee1151920c6","default",1,current.position,current.orientation))
# mouse.program_loop()


# mouse.robot_actions_parse("DobotM1")

"""
while True:
    reading = mouse.mouse.mouse_read()
    print(reading)
    #time.sleep(2)
    print(mouse.move_robot_with_mouse("obj_8b3cd1a403bf44f0abc91691084a1d29","default",reading,1,10))
"""
