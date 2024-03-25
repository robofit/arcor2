import inspect
import json
import os
import sys
import time
from multiprocessing import Process, Queue
from queue import Empty
from tempfile import NamedTemporaryFile

from gtts import gTTS
from pydub import AudioSegment
from pydub.playback import play
from pyspacemouse import SpaceNavigator

from arcor2 import env
from arcor2.data.common import (
    Action,
    ActionParameter,
    ActionPoint,
    Flow,
    LogicItem,
    NamedOrientation,
    Orientation,
    Pose,
    Position,
    Project,
    ProjectRobotJoints,
    Scene,
    StrEnum,
)
from arcor2.data.events import Event
from arcor2.data.rpc import get_id
from arcor2.data.rpc.common import TypeArgs
from arcor2.exceptions import Arcor2Exception
from arcor2_3d_mouse.mouse_controller import MouseFunc, MouseReader
from arcor2_arserver_data import events
from arcor2_arserver_data import rpc as srpc
from arcor2_arserver_data.client import ARServer, ARServerClientException
from arcor2_arserver_data.events.lock import ObjectsLocked, ObjectsUnlocked
from arcor2_arserver_data.events.project import (
    ActionChanged,
    ActionPointChanged,
    JointsChanged,
    LogicItemChanged,
    OpenProject,
    OrientationChanged,
    ProjectClosed,
)
from arcor2_arserver_data.events.robot import RobotMoveToData, RobotMoveToPose
from arcor2_arserver_data.events.scene import SceneState
from arcor2_arserver_data.objects import ObjectAction
from arcor2_execution_data import EVENTS as EXE_EVENTS


class MessageFailException(Arcor2Exception):
    """Custom exception type.

    This exception is raised when a certain event should have been
    received and was not
    """

    pass


class ConditionFailException(Arcor2Exception):
    """Custom exception type.

    This exception is raised when project contains conditions
    """

    pass


class ProgramStateException(Arcor2Exception):
    """Custom exception type.

    This exception is raised when project is not loaded, and program
    expects is to be.
    """

    pass


class RobotActions:
    """Class containing data on an action."""

    def __init__(self, g_name: str, g_desc: str, g_param: list[ActionParameter]) -> None:
        """Init function.

        :param g_name: Name of an action
        :param g_desc: Description of an action
        :param g_param: List of parameters necessary for successful execution of action
        """
        self.name: str = g_name
        self.desc: str = g_desc
        self.parameters: list[ActionParameter] = g_param


class RobotInfo:
    """Class containing data on a robot in scene."""

    def __init__(
        self, g_robot_name: str, g_robot_id: str, g_effector_id: str, g_robot_type: str, g_read_effector: bool
    ) -> None:
        """Init function.

        :param g_robot_name: Name of a robot
        :param g_robot_id: Id of a robot
        :param g_effector_id: Id of robots effector
        :param g_robot_type: Type of a robot
        :param g_read_effector: If robot has multiple effectors
                (default is False)
        """
        self.robot_name: str = g_robot_name
        self.robot_id: str = g_robot_id
        self.effector_id: str = g_effector_id
        self.robot_type: str = g_robot_type
        self.read_effector: bool = g_read_effector

    def get_name(self):
        """Gets name of a robot.

        If robot has multiple effectors it returns string in the format "name - effector"
        otherwise it returns only "name"

        :return: Name of a robot used for audio output
        """
        if self.read_effector:
            return self.robot_name + " - " + self.effector_id
        else:
            return self.robot_name


class ProgramPosition(StrEnum):
    """Class used as an enum.

    Enum used for keeping track of position in program
    """

    WAITING = "waitmenu"
    ROBOTMENU = "robotmenu"
    ACTIONMENU = "actionmenu"
    ROBOTMOVEMENT = "robotmovement"


class MouseProgram:
    """Main class of program."""

    def __init__(self, connection_string: str = "ws://0.0.0.0:6789", timeout: float = 1) -> None:
        """Init function.

        Application initializes class variables and starts separate process
        for reading mouse input.

        :param connection_string: ws://Adress of server:Port of server
        :param timeout: time that the program is willing to wait for server response
            before raising an exception
        """
        self._init_event_mapping()
        self.a_s: ARServer = ARServer(
            ws_connection_str=connection_string, event_mapping=self.event_mapping, timeout=timeout
        )
        request_queue: Queue = Queue()
        receive_queue: Queue = Queue()
        self.process = Process(
            target=self._mouse_reading_process,
            args=(
                request_queue,
                receive_queue,
            ),
        )
        self.process.start()
        self.user_id = env.get_int("G_UID", 1000)
        self.mouse_func: MouseFunc = MouseFunc(request_queue, receive_queue)
        self.program_state: ProgramPosition = ProgramPosition.WAITING
        self.cur_proj: Project | None = None
        self.cur_scene: Scene | None = None
        self.scene_state: bool = False
        self.loaded_robots: list[RobotInfo] | None = None
        self.loaded_actions: list[RobotActions] | None = None
        self.current_robot: RobotInfo | None = None
        self.current_action: RobotActions | None = None
        self.ac_add_counter: int = 0
        self.locked_objects: list[str] = []

    def _init_event_mapping(self):
        """Init for server communication type.

        This function prepares variable used for communicating with
        server used by ARServer class. Created class variable is called
        event_mapping
        """
        self.event_mapping: dict[str, type[Event]] = {evt.__name__: evt for evt in EXE_EVENTS}
        modules = []
        for _, mod in inspect.getmembers(events, inspect.ismodule):
            modules.append(mod)
        for mod in modules:
            for _, cls in inspect.getmembers(mod, inspect.isclass):
                if issubclass(cls, Event):
                    self.event_mapping[cls.__name__] = cls

    def _mouse_read(self):
        """Reads current input from mouse.

        To prevent delay of read input actual reading is done in a separate
        process and shared to main one using Queues.

        :return: input from mouse
        """
        return self.mouse_func.request_reading()

    def _get_event(self) -> Event:
        """Reads event from server.

        :return: event from server

        Raises:
            ARServerClientException
        """
        return self.a_s.get_event()

    def register_user(self, g_name: str) -> srpc.u.RegisterUser.Response:
        """Registers user.

        :param g_name: name of registered user

        :return: Server response
        """
        return self.a_s.call_rpc(
            srpc.u.RegisterUser.Request(get_id(), srpc.u.RegisterUser.Request.Args(user_name=g_name)),
            srpc.u.RegisterUser.Response,
        )

    def _process_event(self, event: Event) -> None:
        """Processes read event.

        Processes event from server and updates local project, based
        on messages from server

        :param event: Event read from server
        """
        if self.cur_proj is not None:
            # Change of action point
            if isinstance(event, ActionPointChanged):
                if event.change_type == Event.Type.ADD:
                    self.cur_proj.action_points.append(ActionPoint.from_bare(event.data))
                if event.change_type == Event.Type.REMOVE:
                    ac_remove_f: ActionPoint | None = next(
                        (ac for ac in self.cur_proj.action_points if ac.id == event.data.id), None
                    )
                    if ac_remove_f is not None:
                        ac_remove: ActionPoint = ac_remove_f
                        self.cur_proj.action_points.remove(ac_remove)
                if event.change_type == Event.Type.UPDATE:
                    ac_update_f: ActionPoint | None = next(
                        (ac for ac in self.cur_proj.action_points if ac.id == event.data.id), None
                    )
                    if ac_update_f is not None:
                        ac_update: ActionPoint = ac_update_f
                        self.cur_proj.action_points.remove(ac_update)
                    self.cur_proj.action_points.append(ActionPoint.from_bare(event.data))
            # Change of logic item
            if isinstance(event, LogicItemChanged):
                if event.change_type == Event.Type.ADD:
                    self.cur_proj.logic.append(event.data)
                if event.change_type == Event.Type.REMOVE:
                    logic_remove_f: LogicItem | None = next(
                        (li for li in self.cur_proj.logic if li.id == event.data.id), None
                    )
                    if logic_remove_f is not None:
                        logic_remove: LogicItem = logic_remove_f
                        self.cur_proj.logic.remove(logic_remove)
                if event.change_type == Event.Type.UPDATE:
                    logic_update_f: LogicItem | None = next(
                        (li for li in self.cur_proj.logic if li.id == event.data.id), None
                    )
                    if logic_update_f is not None:
                        logic_update: LogicItem = logic_update_f
                        self.cur_proj.logic.remove(logic_update)
                    self.cur_proj.logic.append(event.data)
            # Change of Action
            if isinstance(event, ActionChanged):
                if event.change_type == Event.Type.ADD:
                    ap_ac_add: ActionPoint = next(
                        filter(lambda ap: ap.id == event.parent_id, self.cur_proj.action_points)
                    )
                    ac = Action(event.data.name, event.data.type, event.data.id)
                    ap_ac_add.actions.append(ac)
                if event.change_type == Event.Type.REMOVE:
                    ap_ac_rem: ActionPoint = next(
                        filter(lambda ap: ap.id == event.parent_id, self.cur_proj.action_points)
                    )
                    ac_f: Action | None = next((ac for ac in ap_ac_rem.actions if ac.id == event.data.id))
                    if ac_f is not None:
                        ac_rem: Action = ac_f
                        ap_ac_rem.actions.remove(ac_rem)
                if event.change_type == Event.Type.UPDATE:
                    pass
            # Change of orientation
            if isinstance(event, OrientationChanged):
                if event.change_type == Event.Type.ADD:
                    ap_oc_add: ActionPoint = next(
                        filter(lambda ap: ap.id == event.parent_id, self.cur_proj.action_points)
                    )
                    ap_oc_add.orientations.append(event.data)
                if event.change_type == Event.Type.REMOVE:
                    ap_oc_rem: ActionPoint = next(
                        filter(lambda ap: ap.id == event.parent_id, self.cur_proj.action_points)
                    )
                    oc_f: NamedOrientation | None = next(
                        (oc for oc in ap_oc_rem.orientations if oc.id == event.data.id), None
                    )
                    if oc_f is not None:
                        oc_rem: NamedOrientation = oc_f
                        ap_oc_rem.orientations.remove(oc_rem)
                if event.change_type == Event.Type.UPDATE:
                    pass
            # Change of joints
            if isinstance(event, JointsChanged):
                if event.change_type == Event.Type.ADD:
                    ap_jc_add: ActionPoint = next(
                        filter(lambda ap: ap.id == event.parent_id, self.cur_proj.action_points)
                    )
                    ap_jc_add.robot_joints.append(event.data)
                if event.change_type == Event.Type.REMOVE:
                    ap_jc_rem: ActionPoint | None = next(
                        (ap for ap in self.cur_proj.action_points if ap.id == event.parent_id), None
                    )
                    if ap_jc_rem is None:
                        return
                    jc_f: ProjectRobotJoints | None = next(
                        (j for j in ap_jc_rem.robot_joints if j.id == event.data.id), None
                    )
                    if jc_f is not None:
                        jc_rem: ProjectRobotJoints = jc_f
                        ap_jc_rem.robot_joints.remove(jc_rem)
                if event.change_type == Event.Type.UPDATE:
                    pass
            # Change of locks
            if isinstance(event, ObjectsLocked):
                self.locked_objects.extend(x for x in event.data.object_ids)
            if isinstance(event, ObjectsUnlocked):
                for x in event.data.object_ids:
                    if x in self.locked_objects:
                        self.locked_objects.remove(x)
            # Change of project
            if isinstance(event, ProjectClosed):
                self.cur_proj = None
                self.cur_scene = None
                self._read_text("Project has been closed.")
                self.program_state = ProgramPosition.WAITING
        else:
            if isinstance(event, OpenProject):
                self.cur_proj = event.data.project
                self.cur_scene = event.data.scene
                self._read_text("Project opened.")
        # Changes of scene state
        if isinstance(event, SceneState) and event.data.state != "started":
            self._read_text("Scene has been stopped.")
            self.scene_state = False
            self.program_state = ProgramPosition.WAITING
        if isinstance(event, SceneState):
            if event.data.state == "started":
                self.scene_state = True
                self._read_text("Project started")

    def _pop_events(self) -> None:
        """Reads and processes all events sent by server."""
        while 1:
            try:
                event: Event = self._get_event()
                self._process_event(event)
            except ARServerClientException:
                break

    def close_program(self, *args) -> None:
        """Closes program and stops mouse reading process."""
        self.process.kill()
        sys.exit(0)

    def _read_text(self, g_text: str) -> None:
        """Spawns child reading process.

        Spawns child reading process, so the subprocess
        can be run with different user id. This step is
        necessary for sound library to work with docker.

        :param g_text: Text to read
        """
        p = Process(target=self._read_text_process, args=(g_text,))
        p.start()
        p.join()

    def _read_text_process(self, g_text):
        """Reads sent text out loud.

        Uses a gTTS library to convert text to audio and
        pydub to play sounds.

        :param g_text: Text to read
        """
        os.setuid(self.user_id)
        if len(g_text) < 6:
            g_text = "Action " + g_text
        langObj: gTTS = gTTS(text=g_text, lang="en", slow=False)
        with NamedTemporaryFile() as temp:
            langObj.write_to_fp(temp)
            song: AudioSegment = AudioSegment.from_mp3(temp.name)
            play(song)
            temp.close()

    def _lock_write(self, g_id: str, g_lock_tree: bool = False) -> srpc.lock.WriteLock.Response:
        """Locks given object.

        :param g_id: Id of object to lock
        :param g_lock_tree: If it should also lock child objects

        :return: Server response
        """
        return self.a_s.call_rpc(
            srpc.lock.WriteLock.Request(get_id(), srpc.lock.WriteLock.Request.Args(g_id, g_lock_tree)),
            srpc.lock.WriteLock.Response,
        )

    def _lock_write_unlock(self, g_id: str) -> srpc.lock.WriteUnlock.Response:
        """Unlocks given object.

        :param g_id: Id of object to unlock

        :return: Server response
        """
        return self.a_s.call_rpc(
            srpc.lock.WriteUnlock.Request(get_id(), srpc.lock.WriteUnlock.Request.Args(g_id)),
            srpc.lock.WriteUnlock.Response,
        )

    def _robot_end_effector_pose(
        self, g_robot_id: str, g_end_effector_id: str, g_arm_id: str | None = None
    ) -> srpc.r.GetEndEffectorPose.Response:
        """Gets pose of robots end effector.

        :param g_robot_id: Id of robot
        :param g_end_effector: Id robots effector
        :param g_arm_id: Id of robots arm if any

        :return: Server response
        """
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

    def _robot_end_effectors_get(self, g_robot_id: str, g_arm_id: str | None = None) -> srpc.r.GetEndEffectors.Response:
        """Gets list of robots end effectors.

        :param g_robot_id: Id of robot
        :param g_arm_id: Id of robots arm if any

        :return: Server response
        """
        return self.a_s.call_rpc(
            srpc.r.GetEndEffectors.Request(get_id(), srpc.r.GetEndEffectors.Request.Args(g_robot_id, g_arm_id)),
            srpc.r.GetEndEffectors.Response,
        )

    def _robot_move_to_pose(
        self, g_robot_id: str, g_end_effector_id, g_speed: float, g_position: Position, g_orientation: Orientation
    ) -> srpc.r.MoveToPose.Response:
        """Moves robot to pose.

        :param g_robot_id: Id of robot
        :param g_end_effector_id: Id of robots effector
        :param g_speed: Speed of robots movement (0-1)
        :param g_position: target position
        :param g_orientation: target orientation

        :return: Server response
        """
        s_data = srpc.r.MoveToPose.Request.Args(g_robot_id, g_end_effector_id, g_speed, g_position, g_orientation)
        return self.a_s.call_rpc(srpc.r.MoveToPose.Request(get_id(), s_data), srpc.r.MoveToPose.Response)

    def _robot_meta_get(self) -> srpc.r.GetRobotMeta.Response:
        """Gets list of robots recognized by system.

        :return: Server response
        """
        return self.a_s.call_rpc(srpc.r.GetRobotMeta.Request(get_id()), srpc.r.GetRobotMeta.Response)

    def _parse_robot_meta(self) -> list[str]:
        """Parses robot types from robot meta.

        Raises:
            MessageFailException

        :return: list of robot types recognized by system
        """
        response = self._robot_meta_get()
        if response.data is None:
            raise MessageFailException("Failed to get data from server.")
        return [robot.type for robot in response.data]

    def _get_robots_in_scene(self) -> list[RobotInfo]:
        """Returns list of robots in scene.

        Gets list of robot types recognized by system and then
        it compares it to the list of objects in scene to determine
        which objects are robots. Then saves data about these robots
        to list of RobotInfo classes.

        :return: Data about robots in scene

        Raises:
            MessageFailException
        """
        robot_types: list[str] = self._parse_robot_meta()
        robot_list: list[RobotInfo] = []
        if self.cur_scene is None:
            return robot_list
        for obj in self.cur_scene.objects:
            if obj.type in robot_types:
                effectors = self._robot_end_effectors_get(obj.id)
                if not effectors.result:
                    raise MessageFailException(effectors.messages)
                if effectors.data is not None:
                    for effector in effectors.data:
                        robot_list.append(RobotInfo(obj.name, obj.id, effector, obj.type, len(effectors.data) > 1))
        return robot_list

    def _robot_get_actions(self, g_type: str) -> srpc.o.GetActions.Response:
        """Gets list of actions supported by given type.

        :param g_type: Type of robot

        :return: Server response
        """
        return self.a_s.call_rpc(srpc.o.GetActions.Request(get_id(), TypeArgs(g_type)), srpc.o.GetActions.Response)

    def _robot_actions_parse(self, g_type: str) -> list[RobotActions]:
        """Prepares list of robot actions.

        This function gets metadate about actions of given robot type. If all of
        actions parameters are valid and automatically fillable it saves it to
        RobotActions class. List of returned RobotActions classes is offered
        to user for choosing action stage.

        Raise:
            MessageFailException

        :param g_type: Type of robot

        :return: list of actions that user can choose from
        """
        meta_data = self._robot_get_actions(g_type).data
        if meta_data is None:
            raise MessageFailException("Failed to get data from server.")
        ac_list = []
        for a in meta_data:
            if a.disabled:
                continue
            p_list = self._robot_params_parse(a)
            if p_list is None:
                continue
            if not isinstance(a.description, str):
                a.description = ""
            ac_list.append(RobotActions(a.name, a.description, p_list))
        return ac_list

    def _robot_params_parse(self, g_action: ObjectAction) -> list[ActionParameter] | None:
        """Parses Metadata of parameter.

        This function reads metadata of action and checks if all
        parameters are valid for this program. If all parameters are
        valid it returns list of parameters with filled values. If not
        it returns None

        Special condition:
            If one of parameters doesn't have default value but it has
            an enum of allowed values in extra, program tries to read it
            and assignes the first one to parameter.

        :param g_action: Metadata of action

        :return: List of parameters
        """
        param_list = []
        for param_meta in g_action.parameters:
            if param_meta.default_value is None and param_meta.type != "pose":
                try:
                    if param_meta.extra is None:
                        return None
                    extra: dict = json.loads(param_meta.extra)
                    try:
                        allowed = extra["allowed_values"]
                        param_list.append(ActionParameter(param_meta.name, param_meta.type, '"' + allowed[0] + '"'))
                    except KeyError:
                        return None
                except json.decoder.JSONDecodeError:
                    return None
            else:
                if param_meta.default_value is None:
                    param_list.append(ActionParameter(param_meta.name, param_meta.type, "temp"))
                else:
                    param_list.append(ActionParameter(param_meta.name, param_meta.type, param_meta.default_value))
        return param_list

    def _action_add(
        self, g_action_point_id: str, g_name: str, g_type: str, g_params: list[ActionParameter]
    ) -> srpc.p.AddAction.Response:
        """Adds action to project.

        :param g_action_point_id: id of action point
        :param g_name: name of new action
        :param g_type: type of action -> format "robot_id/action_type"
        :param g_params: list of actions parameters

        :return: Server response
        """
        return self.a_s.call_rpc(
            srpc.p.AddAction.Request(
                get_id(),
                srpc.p.AddAction.Request.Args(g_action_point_id, g_name, g_type, parameters=g_params, flows=[Flow()]),
            ),
            srpc.p.AddAction.Response,
        )

    def _action_point_add_by_robot(
        self, g_robot_id: str, g_end_effector_id: str, g_name: str
    ) -> srpc.p.AddApUsingRobot.Response:
        """Adds action point to project by robot.

        :param g_robot_id: id of robot
        :param g_end_effector_id: id of effector
        :param g_name: name of new action point

        :return: Server response
        """
        return self.a_s.call_rpc(
            srpc.p.AddApUsingRobot.Request(
                get_id(), srpc.p.AddApUsingRobot.Request.Args(g_robot_id, g_end_effector_id, g_name)
            ),
            srpc.p.AddApUsingRobot.Response,
        )

    def _logic_add(self, g_start: str, g_end: str) -> srpc.p.AddLogicItem.Response:
        """Adds new logic item to project.

        :param g_start: current action id
        :param g_end: next action id

        :return: Server response
        """
        return self.a_s.call_rpc(
            srpc.p.AddLogicItem.Request(get_id(), srpc.p.AddLogicItem.Request.Args(g_start, g_end)),
            srpc.p.AddLogicItem.Response,
        )

    def _logic_update(self, g_id: str, g_start: str, g_end: str) -> srpc.p.UpdateLogicItem.Response:
        """Updates logic item.

        :param g_id: updated logic item id
        :param g_start: new current action id
        :param g_end: new next action id

        :return: Server response
        """
        return self.a_s.call_rpc(
            srpc.p.UpdateLogicItem.Request(get_id(), srpc.p.UpdateLogicItem.Request.Args(g_id, g_start, g_end)),
            srpc.p.UpdateLogicItem.Response,
        )

    def _find_last_logic(self, logiclist: list[LogicItem]) -> LogicItem | None:
        """Searches for and returns last logic item of program.

        :param logiclist: list of logic items in project

        :return: id of last logic item, None if project has no logic items

        Raises:
            ConditionFailException
        """
        for li in logiclist:
            if li.condition is not None:
                raise ConditionFailException
        start: LogicItem | None = None
        for li in logiclist:
            if li.start == "START":
                start = li
                break
        if start is None:
            return start
        current: LogicItem = start
        while 1:
            if current.end == "END":
                return current
            next: LogicItem | None = None
            for li in logiclist:
                if li.start == current.end:
                    next = li
                    break
            if next is None:
                return current
            current = next

    def _update_logic(self, logiclist: list[LogicItem], new_action: str) -> None:
        """Append new actions to current program.

        If there are conditions in program, program adds new action but does
        not connect it to logic.

        :param logiclist: list of logic items in project
        :param new_action: id of new action
        """
        try:
            last: LogicItem | None = self._find_last_logic(logiclist)
        except ConditionFailException:
            return

        if last is None:
            self._logic_add("START", new_action)
            self._logic_add(new_action, "END")
        else:
            self._logic_update(last.id, last.start, new_action)
            self._logic_add(new_action, "END")

    def _get_mov_pos(
        self, g_robot_id: str, g_end_effector_id: str, g_mouse_reading: SpaceNavigator, g_arm_id: str | None = None
    ) -> Pose:
        """Gets robot target position.

        Gets position of robots effector and calculates new position based on mouse movement.
        Sensitivity value based on testing.

        :param g_robot_id: id of robot
        :param g_end_effector_id: id of robots effector
        :param g_mouse_reading: input from mouse
        :param g_arm_id: id of robots arm, if any

        Raises:
            MessageFaileException

        :return: calculated target pose
        """
        g_sensitivity: float = 0.015
        def_pos_message: srpc.r.GetEndEffectorPose.Response = self._robot_end_effector_pose(
            g_robot_id, g_end_effector_id, g_arm_id
        )
        if def_pos_message.data is None:
            raise MessageFailException("Failed to get robot effector position")
        def_pos: Pose = def_pos_message.data
        def_pos.position.x += g_mouse_reading.x * g_sensitivity
        def_pos.position.y += g_mouse_reading.y * g_sensitivity
        def_pos.position.z += g_mouse_reading.z * g_sensitivity

        return def_pos

    def _get_rot_pos(
        self, g_robot_id: str, g_end_effector_id: str, g_mouse_reading: SpaceNavigator, g_arm_id: str | None = None
    ) -> Pose:
        """Gets robot target rotation.

        Gets rotation of robots effector and calculates new rotation based on mouse movement.
        Sensitivity value based on testing.

        :param g_robot_id: id of robot
        :param g_end_effector_id: id of robots effector
        :param g_mouse_reading: input from mouse
        :param g_arm_id: id of robots arm, if any

        Raises:
            MessageFailException

        :return: calculated target pose
        """
        g_sensitivity: float = 0.015
        def_pos_message: srpc.r.GetEndEffectorPose.Response = self._robot_end_effector_pose(
            g_robot_id, g_end_effector_id, g_arm_id
        )
        if def_pos_message.data is None:
            raise MessageFailException("Failed to get robot effector position")
        def_pos: Pose = def_pos_message.data

        def_pos.orientation *= Orientation().from_rotation_vector(
            g_mouse_reading.roll * g_sensitivity,
            g_mouse_reading.pitch * g_sensitivity,
            g_mouse_reading.yaw * g_sensitivity,
        )
        return def_pos

    def _register_for_robot_event(self, g_robot_id: str, send: bool) -> srpc.r.RegisterForRobotEvent.Response:
        """Registers user to receive events involving chosen robot.

        :param g_robot_id: id of robot
        :param send: if user wants to receive events involving this robot

        :return: Server response
        """
        enum = srpc.r.RegisterForRobotEvent.Request.Args.RegisterEnum.EEF_POSE
        return self.a_s.call_rpc(
            srpc.r.RegisterForRobotEvent.Request(
                get_id(), srpc.r.RegisterForRobotEvent.Request.Args(g_robot_id, enum, send)
            ),
            srpc.r.RegisterForRobotEvent.Response,
        )

    def _prepare_poses(self, def_pose: Pose) -> list[Pose]:
        """Prepares poses for highligthing robot.

        Every pose moves robot in one direction from beginning position
        except down. Robot's movement to target pose shows user which robot
        is selected

        :param def_pose: beginning pose of robot

        :returns: returns list of poses
        """
        p1: Pose = Pose()
        p2: Pose = Pose()
        p3: Pose = Pose()
        p4: Pose = Pose()
        p5: Pose = Pose()
        pos_offset: float = 0.01
        p1.position = Position(def_pose.position.x, def_pose.position.y, def_pose.position.z + pos_offset)
        p2.position = Position(def_pose.position.x + pos_offset, def_pose.position.y, def_pose.position.z)
        p3.position = Position(def_pose.position.x - pos_offset, def_pose.position.y, def_pose.position.z)
        p4.position = Position(def_pose.position.x, def_pose.position.y + pos_offset, def_pose.position.z)
        p5.position = Position(def_pose.position.x, def_pose.position.y - pos_offset, def_pose.position.z)
        return [p1, p2, p3, p4, p5]

    def _highligth_robot_mechanic(self, g_robot_id: str, g_end_effector_id: str, g_arm_id: str | None = None) -> bool:
        """Highlights robot.

        Robot has to move to show if he was selected. One move
        and return to starting position is enough for this. But
        robots movement can fail if direction is out of his bound
        system is aware of this and tries to move him in every direction
        if robot has moved, it returns to it's original location and
        function returns true. If all possible directions, except down
        fail, function returns false and program uses audio cues to show
        selected robot.

        :param g_robot_id: id of robot
        :param g_end_effector_id: id of robots effector
        :param g_arm_id: if of robots arm, if any

        :return: if robot had moved
        """
        self._register_for_robot_event(g_robot_id, True)
        response = self._robot_end_effector_pose(g_robot_id, g_end_effector_id, g_arm_id)
        if response.data is None:
            return False
        def_pos: Pose = response.data
        poses: list[Pose] = self._prepare_poses(def_pos)
        moved: bool = False
        for pose in poses:
            self._robot_move_to_pose(g_robot_id, g_end_effector_id, 0.5, pose.position, def_pos.orientation)
            moved = self._wait_for_movement()
            if self.program_state == ProgramPosition.WAITING:
                return True
            if moved:
                break
        if moved:
            self._robot_move_to_pose(g_robot_id, g_end_effector_id, 0.5, def_pos.position, def_pos.orientation)
            self._wait_for_movement()
            if self.program_state == ProgramPosition.WAITING:
                return True
            self._register_for_robot_event(g_robot_id, False)
        self._register_for_robot_event(g_robot_id, False)
        return moved

    def program_loop(self) -> None:
        """Main program loop.

        Based on programs position corresponding loop is executed.

        :return:
        """
        self._read_text("Program started.")
        while 1:
            self._pop_events()
            if self.program_state == ProgramPosition.WAITING:
                self._waiting_loop()
            if self.program_state == ProgramPosition.ROBOTMENU:
                self._robot_layer_loop()
            if self.program_state == ProgramPosition.ACTIONMENU:
                self._action_layer_loop()
            if self.program_state == ProgramPosition.ROBOTMOVEMENT:
                self._robot_movement_loop()

    def _waiting_loop(self) -> None:
        """Waiting loop.

        No project is open or scene has not started. Program reads
        events and if project is opened and scene is started it moves to
        robot choosing phase.

        :return:
        """
        timer = 10
        while 1:
            reading = self._mouse_read()
            if timer == 10:
                self._pop_events()
                if self.cur_proj is not None and self.cur_scene is not None and self.scene_state:
                    self.program_state = ProgramPosition.ROBOTMENU
                    break
                timer = 0
            if self.mouse_func.mouse_button_right_pressed(reading):
                self.close_program()
            timer += 1
            time.sleep(0.1)

    def _robot_layer_loop(self) -> None:
        """Robot choosing loop.

        Program chooses first unlocked robot in program. After that it
        reads input from mouse and processes user commands. Possible
        outcomes:
            Event ProjectClosed or SceneState stopped read:
                Returns to waiting loop
            User presses LMB and all robots are locked:
                Audio cue, no action
            User presses LMB:
                Program moves to action choosing
            User moves mouse left:
                Next unlocked robot left of selected is selected
            User moves mouse right:
                Next unlocked robot right of selected is selected
            User moves mouse backwards:
                Audio cue for robots name is read
            User presses RMB:
                Program shuts down

        :return:
        """
        self.loaded_robots = self._get_robots_in_scene()
        index = 0
        locked: bool = True
        moved: bool = False
        if index != -1:
            moved = self._highligth_robot_mechanic(
                self.loaded_robots[index].robot_id, self.loaded_robots[index].effector_id
            )
            if self.program_state == ProgramPosition.WAITING:
                return
            if not moved:
                self._read_text(self.loaded_robots[index].get_name())
        else:
            locked = False
            self._read_text("All robots locked")
        while 1:
            reading: SpaceNavigator = self._mouse_read()
            lb_pressed: bool = self.mouse_func.mouse_button_left_pressed(reading)
            rb_pressed: bool = self.mouse_func.mouse_button_right_pressed(reading)
            if lb_pressed:
                if not locked:
                    self._read_text("No robot chosen")
                else:
                    self._read_text("Chosen" + self.loaded_robots[index].get_name())
                    self.current_robot = self.loaded_robots[index]
                    self.program_state = ProgramPosition.ACTIONMENU
                    return
            if rb_pressed:
                self.close_program()
            if self.mouse_func.menu_left_movement(reading):
                index = self._lock_next_left(index)
                if index == -1:
                    self._read_text("All robots locked")
                else:
                    moved = self._highligth_robot_mechanic(
                        self.loaded_robots[index].robot_id, self.loaded_robots[index].effector_id
                    )
                    if self.program_state == ProgramPosition.WAITING:
                        return
                    if not moved:
                        self._read_text(self.loaded_robots[index].get_name())
            if self.mouse_func.menu_right_movement(reading):
                index = self._lock_next_right(index, False)
                if index == -1:
                    self._read_text("All robots locked")
                else:
                    moved = self._highligth_robot_mechanic(
                        self.loaded_robots[index].robot_id, self.loaded_robots[index].effector_id
                    )
                    if self.program_state == ProgramPosition.WAITING:
                        return
                    if not moved:
                        self._read_text(self.loaded_robots[index].get_name())
            if self.mouse_func.menu_top_movement(reading):
                if index != -1:
                    self._read_text(self.loaded_robots[index].get_name())
                else:
                    self._read_text("All robots locked")

    def _lock_next_right(self, index: int, first: bool) -> int:
        if self.loaded_robots is None:
            return -1
        if first:
            if self._lock_write(self.loaded_robots[index].robot_id).result:
                return index
        temp_ind: int = index
        index += 1
        while index != temp_ind:
            index = self._clamp_index(index, 0, self.loaded_robots.__len__() - 1)
            return index
        if self._lock_write(self.loaded_robots[index].robot_id).result:
            return index
        return -1

    def _lock_next_left(self, index: int) -> int:
        temp_ind: int = index
        index -= 1
        if self.loaded_robots is None:
            return index
        while index != temp_ind:
            index = self._clamp_index(index, 0, self.loaded_robots.__len__() - 1)
            return index
        if self._lock_write(self.loaded_robots[index].robot_id).result:
            return index
        return -1

    def _action_layer_loop(self) -> None:
        """Action choosing loop.

        Program reads input from mouse and processes user commands.
        Possible outcomes:
            Event ProjectClosed or SceneState stopped read:
                Returns to waiting loop
            User presses LMB:
                Action chosen
            User moves mouse left:
                Next action left of selected is selected
            User moves mouse right:
                next action right of selected is selected
            User moves mouse backwards:
                Audio cue for actions description
            User presses RMB:
                Program goes back to robot choosing phase
        Raises:
            Program state exception
        :return:
        """
        index: int = 0
        if self.current_robot is None:
            raise ProgramStateException("Actions failed to load.")
        self.loaded_actions = self._robot_actions_parse(self.current_robot.robot_type)
        self._read_text(self.loaded_actions[index].name)
        while 1:
            reading: SpaceNavigator = self._mouse_read()
            lb_pressed: bool = self.mouse_func.mouse_button_left_pressed(reading)
            rb_pressed: bool = self.mouse_func.mouse_button_right_pressed(reading)
            if lb_pressed:
                self._read_text("chosen" + self.loaded_actions[index].name)
                self.current_action = self.loaded_actions[index]
                self.program_state = ProgramPosition.ROBOTMOVEMENT
                return
            if rb_pressed:
                self.current_robot = None
                self.program_state = ProgramPosition.ROBOTMENU
                self.loaded_actions = None
                return
            if self.mouse_func.menu_left_movement(reading):
                index -= 1
                index = self._clamp_index(index, 0, self.loaded_actions.__len__() - 1)
                self._read_text(self.loaded_actions[index].name)
            if self.mouse_func.menu_right_movement(reading):
                index += 1
                index = self._clamp_index(index, 0, self.loaded_actions.__len__() - 1)
                self._read_text(self.loaded_actions[index].name)
            if self.mouse_func.menu_top_movement(reading):
                self._read_text(self.loaded_actions[index].desc)

    def _robot_movement_loop(self) -> None:
        """Robot movement loop.

        Program reads input from mouse and moves chosen robot
        accordingly.
        Possible outcomes:
            Event ProjectClosed orSceneState stopped read:
                Returns to waiting loop
            User presses LMB:
                Program adds new action
            User presses RMB:
                Program goes back to action choosing phase

        Raises:
            Program state exception
        :return:
        """
        if self.current_robot is None:
            raise ProgramStateException("No robot selected.")
        robot_id: str = self.current_robot.robot_id
        effector_id: str = self.current_robot.effector_id
        self._register_for_robot_event(robot_id, True)
        while True:
            reading: SpaceNavigator = self._mouse_read()
            lb_pressed: bool = self.mouse_func.mouse_button_left_pressed(reading)
            rb_pressed: bool = self.mouse_func.mouse_button_right_pressed(reading)
            if self._treshold_check(reading.x, reading.y, reading.z, 0.1) or self._treshold_check(
                reading.roll, reading.pitch, reading.yaw, 45
            ):
                input_type: bool = self._get_input_type(reading)
                if not input_type:
                    pose = self._get_mov_pos(robot_id, effector_id, reading)
                else:
                    pose = self._get_rot_pos(robot_id, effector_id, reading)
                try:
                    self._robot_move_to_pose(robot_id, effector_id, 0.5, pose.position, pose.orientation)
                    self._wait_for_movement()
                except MessageFailException:
                    pass
                if self.program_state == ProgramPosition.WAITING:
                    return
            if lb_pressed:
                self._register_for_robot_event(robot_id, False)
                self._finish_action()
                self.current_action = None
                self.program_state = ProgramPosition.ACTIONMENU
                return
            if rb_pressed:
                self.program_state = ProgramPosition.ACTIONMENU
                self.current_action = None
                self._register_for_robot_event(robot_id, False)
                return

    def _get_input_type(self, reading: SpaceNavigator) -> bool:
        """Get dominant input type.

        There was an error when robot tried to move and rotate
        at the same time when robot was physically unable to
        rotate. To prevent incorrect inputs program reads
        every input and decides which is dominant translation
        or rotation and does only the dominant command. User is
        usually unable to translate and rotate at the same time
        as well

        :param reading: input from mouse

        :return: False if translation is dominant True if
            rotation is dominant
        """
        move_values: list[float] = [reading.x, reading.y, reading.z]
        rot_values: list[float] = [reading.roll, reading.pitch, reading.yaw]
        move_max = max(max(move_values), self._mabs(min(move_values)))
        rot_max = max(max(rot_values), self._mabs(min(rot_values)))
        return rot_max > move_max

    def _finish_action(self):
        """Program adds new action.

        Program first adds new action point and reads corresponding
        events. After that it adds new action and reads events again.
        And lastly it appends new action to program.

        Raises:
            Program state exception

        :return:
        """
        if self.cur_proj is None or self.current_robot is None or self.current_action is None:
            raise ProgramStateException("Failed to complete action.")
        robot_id = self.current_robot.robot_id
        eff_id = self.current_robot.effector_id
        action_name = self.current_action.name
        point_name = "Action_" + str(self.ac_add_counter) + "_" + robot_id + "_" + eff_id + "_" + action_name
        self.ac_add_counter += 1
        self._action_point_add_by_robot(robot_id, eff_id, point_name)
        self._pop_events()
        if self.program_state == ProgramPosition.WAITING:
            return
        ap: ActionPoint = self._get_added_point(point_name)
        self._lock_write(ap.id, True)
        orientation_id = ap.orientations[0].id
        for param in self.current_action.parameters:
            if param.type == "pose":
                param.value = '"' + orientation_id + '"'
        self._action_add(
            ap.id, point_name + "ac", robot_id + "/" + self.current_action.name, self.current_action.parameters
        )
        self._pop_events()
        if self.program_state == ProgramPosition.WAITING or self.cur_proj is None:
            return  # type: ignore
        self._update_logic(self.cur_proj.logic, ap.actions[0].id)
        self._lock_write_unlock(ap.id)
        self._pop_events()
        if self.program_state == ProgramPosition.WAITING:
            return  # type: ignore

    def _get_added_point(self, name: str) -> ActionPoint:
        """Gets newly added action point.

        :param name: Name of new action point

        :return: Added action point
        """
        id = None
        if self.cur_proj is None:
            raise ProgramStateException("Failed to add new action point")
        for ap in reversed(self.cur_proj.action_points):
            if ap.name == name:
                id = ap.id
                break
        if id is None:
            raise MessageFailException("Failed to add new action point")
        return next(filter(lambda ap: ap.id == id, self.cur_proj.action_points))

    def _clamp_index(self, number: int, l_clamp: int, r_clamp: int) -> int:
        """Helper function for clamping index to array size.

        :param number: value to clamp
        :param l_clamp: value of left barrier
        :param r_clamp: value of right barrier

        :return: clamped value
        """
        if number < l_clamp:
            return r_clamp
        if number > r_clamp:
            return l_clamp
        return number

    def _mabs(self, x: float) -> float:
        """Returns absolute value.

        :param x: given value

        :return: absolute value
        """
        return x if x > 0 else -x

    def _treshold_check(self, x: float, y: float, z: float, threshold: float) -> bool:
        """Checks if given values are bigger than the threshold.

        Used to reduce noise from reading from mouse.

        :param x: x position of mouse
        :param y: y position of mouse
        :param z: z position of mouse
        :param treshold: treshold value

        :return: if absolute value of given value is bigger than threshold
            returns True, else returns False
        """
        return self._mabs(x) > threshold or self._mabs(y) > threshold or self._mabs(z) > threshold

    def _wait_for_movement(self) -> bool:
        """Waits until robot reached target position.

        Reads and processes incoming events until it reads
        event RobotMoveToPose had ended or failed.

        Raises:
            MessageFailException
        """
        while 1:
            event = None
            try:
                event = self._get_event()
            except ARServerClientException:
                raise MessageFailException("No event received from server.")
            if isinstance(event, RobotMoveToPose):
                if event.data.move_event_type == RobotMoveToData.MoveEventType.END:
                    return True
                if event.data.move_event_type == RobotMoveToData.MoveEventType.FAILED:
                    return False
            else:
                self._process_event(event)

    def _mouse_reading_process(self, request_queue: Queue, receive_queue: Queue) -> None:
        """Loop for mouse reading process.

        Mouse reading process goes in a loop that reads input values.
        If it reads input value in requst queue, it puts current mouse
        input into receive queue. Method Queue.empty() exists, but it
        was described as unreliable in documentation, and because of that
        I use catching exceptions instead.

        :param request_queue: Queue for requests
        :param receive_queue: Queue for responses
        :return:
        """
        mouse = MouseReader()
        time.sleep(1)
        while True:
            reading = mouse.mouse_read()
            try:
                request_queue.get(block=False, timeout=0.05)
                receive_queue.put(reading)
            except Empty:
                pass
