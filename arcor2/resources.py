#!/usr/bin/env python3
# -*- coding: utf-8 -*-


from os import path
from typing import Dict, Union, Type, TypeVar, List, Optional, get_type_hints, Any, Tuple
import importlib
import json

from dataclasses_jsonschema import JsonSchemaValidationError, JsonSchemaMixin

from arcor2.object_types_utils import built_in_types_names
from arcor2.data.common import Project, Scene, ActionPoint, ActionParameterTypeEnum, ActionParameter, \
    CurrentAction, StrEnum, IntEnum, Pose
from arcor2.data.object_type import ObjectModel, Models, ObjectActionArg
from arcor2.data.events import CurrentActionEvent
from arcor2.exceptions import ResourcesException, Arcor2Exception
import arcor2.object_types
from arcor2.object_types import Generic
from arcor2.services import Service, RobotService
from arcor2.action import print_event
from arcor2.settings import PROJECT_PATH
from arcor2.rest import convert_keys
from arcor2.helpers import camel_case_to_snake_case, make_position_abs, make_orientation_abs, print_exception
from arcor2.object_types_utils import meta_from_def, object_actions


# TODO for bound methods - check whether provided action point belongs to the object

class IntResources:

    CUSTOM_OBJECT_TYPES_MODULE = "object_types"
    SERVICES_MODULE = "services"

    def __init__(self, scene: Scene, project: Project, models: Dict[str, Optional[Models]]) -> None:

        self.project = project
        self.scene = scene

        if self.project.scene_id != self.scene.id:
            raise ResourcesException("Project/scene not consistent!")

        self.action_args: Dict[str, Dict[str, Dict[str, ObjectActionArg]]] = {}  # keys: obj_type, action_name, arg_name
        self.action_id_to_type_and_action_name: Dict[str, Tuple[str, str]] = {}

        self.services: Dict[str, Service] = {}
        self.objects: Dict[str, Generic] = {}

        self.robot_service: Optional[RobotService] = None

        type_defs: List[Union[Type[Service], Type[Generic]]] = []

        for srv in self.scene.services:

            assert srv.type not in self.services, "Duplicate service {}!".format(srv.type)

            module = importlib.import_module(ResourcesBase.SERVICES_MODULE + "." + camel_case_to_snake_case(srv.type))
            cls = getattr(module, srv.type)
            assert issubclass(cls, Service)

            srv_inst = cls(srv.configuration_id)
            type_defs.append(cls)
            self.services[srv.type] = srv_inst

            if isinstance(srv_inst, RobotService):
                assert self.robot_service is None
                self.robot_service = srv_inst

        built_in = built_in_types_names()

        for scene_obj in self.scene.objects:

            if scene_obj.type in built_in:
                module = importlib.import_module(arcor2.object_types.__name__ + "." +
                                                 camel_case_to_snake_case(scene_obj.type))
            else:
                module = importlib.import_module(ResourcesBase.CUSTOM_OBJECT_TYPES_MODULE + "." +
                                                 camel_case_to_snake_case(scene_obj.type))

            cls = getattr(module, scene_obj.type)
            type_defs.append(cls)

            assert scene_obj.id not in self.objects, "Duplicate object id {}!".format(scene_obj.id)

            if hasattr(cls, "from_services"):

                obj_meta = meta_from_def(cls)

                args: List[Service] = []

                for srv_type in obj_meta.needs_services:
                    args.append(self.services[srv_type])

                inst = cls(*args, scene_obj.id, scene_obj.pose, models[scene_obj.type])
            else:
                inst = cls(scene_obj.id, scene_obj.pose, models[scene_obj.type])

            self.objects[scene_obj.id] = inst

            if self.robot_service:
                self.robot_service.add_collision(inst)

        self.all_instances: Dict[str, Union[Generic, Service]] = dict(**self.objects, **self.services)

        # add action points to the object_types
        for project_obj in self.project.objects:
            for aps in project_obj.action_points:

                obj_inst = self.objects[project_obj.id]

                for action in aps.actions:
                    assert action.id not in self.action_id_to_type_and_action_name
                    action_obj_id, action_type = action.parse_type()
                    self.action_id_to_type_and_action_name[action.id] = \
                        self.all_instances[action_obj_id].__class__.__name__, action_type

                # Action point pose is relative to its parent object pose in scene but is absolute during runtime.
                obj_inst.action_points[aps.id] = aps
                aps.position = make_position_abs(obj_inst.pose.position, aps.position)
                for ori in aps.orientations:
                    ori.orientation = make_orientation_abs(obj_inst.pose.orientation, ori.orientation)

        for type_def in type_defs:

            self.action_args[type_def.__name__] = {}
            for obj_action in object_actions(type_def):
                self.action_args[type_def.__name__][obj_action.name] = {}
                for arg in obj_action.action_args:
                    self.action_args[type_def.__name__][obj_action.name][arg.name] = arg

    def __enter__(self):
        return self

    def __exit__(self, ex_type, ex_value, traceback):  # TODO check for exception and print it

        if ex_type:  # TODO ignore when script is stopped correctly (e.g. KeyboardInterrupt, ??)
            print_exception(ex_type(ex_value))

        if self.robot_service:
            try:
                for obj in self.objects.values():
                    self.robot_service.remove_collision(obj)
            except Arcor2Exception as e:
                print_exception(e)

        return True

    def print_info(self, action_id: str, args: Dict[str, Any]) -> None:
        """Helper method used to print out info about the action going to be executed."""

        args_list: List[ActionParameter] = []

        for k, v in args.items():

            vv = v

            # this is needed because of "value: Any"
            if hasattr(v, "to_dict"):
                vv = v.to_dict()  # type: ignore
            elif isinstance(v, (StrEnum, IntEnum)):
                vv = v.value

            obj_type_name, action_name = self.action_id_to_type_and_action_name[action_id]
            arg = self.action_args[obj_type_name][action_name][k]
            args_list.append(ActionParameter(k, vv, arg.type))

        print_event(CurrentActionEvent(data=CurrentAction(action_id, args_list)))

    def action_point(self, object_id: str, ap_id: str) -> ActionPoint:

        try:
            return self.objects[object_id].action_points[ap_id]
        except KeyError:
            raise ResourcesException("Unknown object id or action point id.")

    def parameters(self, action_id: str) -> Dict[str, Any]:

        try:
            act = self.project.action(action_id)
        except Arcor2Exception:
            raise ResourcesException("Action_id {} not found in project {}.".format(action_id, self.project.id))

        inst_name, method_name = act.type.split("/")
        action_obj_inst = self.all_instances[inst_name]

        ret: Dict[str, Any] = {}

        for param in act.parameters:
            if param.type in (ActionParameterTypeEnum.POSE, ActionParameterTypeEnum.JOINTS):
                assert isinstance(param.value, str)
                try:
                    object_id, ap_id, value_id = param.parse_id()
                except Arcor2Exception:
                    raise ResourcesException(f"Action {act.id} has invalid value {param.value}"
                                             f" for parameter: {param.id}.")

                if param.type == ActionParameterTypeEnum.POSE:
                    ret[param.id] = self.action_point(object_id, ap_id).pose(value_id)
                elif param.type == ActionParameterTypeEnum.JOINTS:

                    robot_id = inst_name

                    if isinstance(action_obj_inst, RobotService):
                        for aparam in act.parameters:
                            if aparam.type == ActionParameterTypeEnum.STRING and aparam.id == "robot_id":
                                robot_id = aparam.value
                                break
                        else:
                            raise ResourcesException(f"Parameter 'robot_id' of type string needed by"
                                                     f" {param.id} not found.")

                    ret[param.id] = self.action_point(object_id, ap_id).get_joints(robot_id, value_id)

            elif param.type == ActionParameterTypeEnum.RELATIVE_POSE:
                assert isinstance(param.value, dict)
                ret[param.id] = Pose.from_dict(param.value)  # TODO do this in __post_init__ of ActionPoint?

            elif param.type in (ActionParameterTypeEnum.STRING_ENUM,
                                ActionParameterTypeEnum.INTEGER_ENUM):

                method = getattr(action_obj_inst, method_name)
                ttype = get_type_hints(method)[param.id]
                ret[param.id] = ttype(param.value)

            else:
                ret[param.id] = param.value

        return ret


T = TypeVar('T', bound=JsonSchemaMixin)


def lower(s: str) -> str:

    return s.lower()


class ResourcesBase(IntResources):

    def read_project_data(self, file_name: str, cls: Type[T]) -> T:

        try:

            with open(path.join(PROJECT_PATH, "data", file_name + ".json")) as scene_file:

                data_dict = json.loads(scene_file.read())
                data_dict = convert_keys(data_dict, camel_case_to_snake_case)

                return cls.from_dict(data_dict)

        except JsonSchemaValidationError as e:
            raise ResourcesException(f"Invalid project/scene: {e}")

    def __init__(self, project_id: str) -> None:

        scene = self.read_project_data(Scene.__name__.lower(), Scene)
        project = self.read_project_data(Project.__name__.lower(), Project)

        if project_id != project.id:
            raise ResourcesException("Resources were generated for different project!")

        models: Dict[str, Optional[Models]] = {}

        for obj in scene.objects:

            if obj.type in models:
                continue

            try:
                models[obj.type] = self.read_project_data(camel_case_to_snake_case(obj.type), ObjectModel).model()
            except IOError:
                models[obj.type] = None

        super(ResourcesBase, self).__init__(scene, project, models)
