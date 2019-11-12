#!/usr/bin/env python3
# -*- coding: utf-8 -*-


from os import path
from typing import Dict, Union, Type, TypeVar, List
import importlib
import json

from dataclasses_jsonschema import JsonSchemaValidationError, JsonSchemaMixin

from arcor2.object_types_utils import built_in_types_names
from arcor2.data.common import Project, Scene, ActionPoint, ActionParameterTypeEnum, ActionParameter, \
    ARGS_MAPPING, SUPPORTED_ARGS, CurrentAction
from arcor2.data.events import CurrentActionEvent
from arcor2.exceptions import ResourcesException
import arcor2.object_types
from arcor2.object_types import Generic
from arcor2.services import Service
from arcor2.action import print_event
from arcor2.settings import PROJECT_PATH
from arcor2.rest import convert_keys
from arcor2.helpers import camel_case_to_snake_case, make_pose_abs
from arcor2.object_types_utils import meta_from_def


# TODO for bound methods - check whether provided action point belongs to the object


ARGS_DICT = Dict[str, SUPPORTED_ARGS]


class IntResources:

    CUSTOM_OBJECT_TYPES_MODULE = "object_types"
    SERVICES_MODULE = "services"

    def __init__(self, scene: Scene, project: Project) -> None:

        self.project = project
        self.scene = scene

        if self.project.scene_id != self.scene.id:
            raise ResourcesException("Project/scene not consistent!")

        self.services: Dict[str, Service] = {}
        self.objects: Dict[str, Generic] = {}

        for srv in self.scene.services:

            assert srv.type not in self.services, "Duplicate service {}!".format(srv.type)

            module = importlib.import_module(ResourcesBase.SERVICES_MODULE + "." + camel_case_to_snake_case(srv.type))
            cls = getattr(module, srv.type)
            self.services[srv.type] = cls(srv.configuration_id)

        built_in = built_in_types_names()

        for scene_obj in self.scene.objects:

            if scene_obj.type in built_in:
                module = importlib.import_module(arcor2.object_types.__name__ + "." +
                                                 camel_case_to_snake_case(scene_obj.type))
            else:
                module = importlib.import_module(ResourcesBase.CUSTOM_OBJECT_TYPES_MODULE + "." +
                                                 camel_case_to_snake_case(scene_obj.type))

            cls = getattr(module, scene_obj.type)

            assert scene_obj.id not in self.objects, "Duplicate object id {}!".format(scene_obj.id)

            if hasattr(cls, "from_services"):

                obj_meta = meta_from_def(cls)

                args: List[Service] = []

                for srv_type in obj_meta.needs_services:
                    args.append(self.services[srv_type])

                inst = cls(*args, scene_obj.id, scene_obj.pose)
            else:
                inst = cls(scene_obj.id, scene_obj.pose)

            self.objects[scene_obj.id] = inst

        # add action points to the object_types
        for project_obj in self.project.objects:

            for aps in project_obj.action_points:
                # Action point pose is relative to its parent object pose in scene but is absolute during runtime.
                abs_pose = make_pose_abs(self.objects[project_obj.id].pose, aps.pose)
                self.objects[project_obj.id].add_action_point(aps.id, abs_pose)

    @staticmethod
    def print_info(action_id: str, args: ARGS_DICT) -> None:
        """Helper method used to print out info about the action going to be executed."""

        args_list: List[ActionParameter] = []

        for k, v in args.items():

            vv: Union[SUPPORTED_ARGS, Dict] = v

            if isinstance(v, ActionPoint):  # this is needed because of "value: Any"
                vv = v.to_dict()

            args_list.append(ActionParameter(k, ARGS_MAPPING[type(v)], vv))

        print_event(CurrentActionEvent(data=CurrentAction(action_id, args_list)))

    def action_point(self, object_id: str, ap_id: str) -> ActionPoint:

        try:
            return self.objects[object_id].action_points[ap_id]
        except KeyError:
            raise ResourcesException("Unknown object id or action point id.")

    def parameters(self, action_id: str) -> ARGS_DICT:

        for obj in self.project.objects:
            for aps in obj.action_points:
                for act in aps.actions:
                    if act.id == action_id:

                        ret: Dict[str, Union[str, float, int, ActionPoint]] = {}

                        for param in act.parameters:
                            if param.type == ActionParameterTypeEnum.ACTION_POINT:
                                assert isinstance(param.value, str)
                                object_id, ap_id = param.value.split('.')
                                ret[param.id] = self.action_point(object_id, ap_id)
                            else:
                                ret[param.id] = param.value

                        return ret

        raise ResourcesException("Action_id {} not found for project {}.".format(action_id, self.project.id))


T = TypeVar('T', bound=JsonSchemaMixin)


def lower(s: str) -> str:

    return s.lower()


class ResourcesBase(IntResources):

    def read_project_data(self, cls: Type[T]) -> T:

        try:

            with open(path.join(PROJECT_PATH, "data", cls.__name__.lower() + ".json")) as scene_file:

                data_dict = json.loads(scene_file.read())
                data_dict = convert_keys(data_dict, camel_case_to_snake_case)

                return cls.from_dict(data_dict)

        except JsonSchemaValidationError as e:
            raise ResourcesException(f"Invalid project/scene: {e}")
        except IOError as e:
            raise ResourcesException(f"Failed to read project/scene: {e}")

    def __init__(self, project_id: str) -> None:

        scene = self.read_project_data(Scene)
        project = self.read_project_data(Project)

        if project_id != project.id:
            raise ResourcesException("Resources were generated for different project!")

        super(ResourcesBase, self).__init__(scene, project)
