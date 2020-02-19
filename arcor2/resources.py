#!/usr/bin/env python3
# -*- coding: utf-8 -*-


from os import path
from typing import Dict, Union, TypeVar, List, Optional, Any, Type
import importlib
import json

from dataclasses_jsonschema import JsonSchemaValidationError, JsonSchemaMixin

from arcor2.object_types_utils import built_in_types_names
from arcor2.data.common import Project, Scene, CurrentAction
from arcor2.data.object_type import ObjectModel, Models
from arcor2.data.events import CurrentActionEvent
from arcor2.exceptions import ResourcesException, Arcor2Exception
import arcor2.object_types
from arcor2.object_types import Generic
from arcor2.services import Service, RobotService
from arcor2.action import print_event
from arcor2.rest import convert_keys
from arcor2.helpers import camel_case_to_snake_case, make_position_abs, make_orientation_abs, print_exception
import arcor2.object_types_utils as otu

from arcor2.parameter_plugins import PARAM_PLUGINS
from arcor2.parameter_plugins.base import TypesDict


# TODO for bound methods - check whether provided action point belongs to the object

class IntResources:

    CUSTOM_OBJECT_TYPES_MODULE = "object_types"
    SERVICES_MODULE = "services"

    def __init__(self, scene: Scene, project: Project, models: Dict[str, Optional[Models]]) -> None:

        self.project = project
        self.scene = scene

        if self.project.scene_id != self.scene.id:
            raise ResourcesException("Project/scene not consistent!")

        self.services: Dict[str, Service] = {}
        self.objects: Dict[str, Generic] = {}

        self.robot_service: Optional[RobotService] = None

        self.type_defs: TypesDict = {}

        for srv in self.scene.services:

            assert srv.type not in self.services, "Duplicate service {}!".format(srv.type)

            module = importlib.import_module(ResourcesBase.SERVICES_MODULE + "." + camel_case_to_snake_case(srv.type))
            cls = getattr(module, srv.type)
            assert issubclass(cls, Service)

            srv_inst = cls(srv.configuration_id)
            self.type_defs[cls.__name__] = cls
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
            self.type_defs[cls.__name__] = cls

            assert scene_obj.id not in self.objects, "Duplicate object id {}!".format(scene_obj.id)

            if hasattr(cls, "from_services"):

                obj_meta = otu.meta_from_def(cls)

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

        # make all poses absolute
        for project_obj in self.project.objects:
            for aps in project_obj.action_points:

                obj_inst = self.objects[project_obj.id]

                # Action point pose is relative to its parent object pose in scene but is absolute during runtime.
                obj_inst.action_points[aps.id] = aps
                aps.position = make_position_abs(obj_inst.pose.position, aps.position)
                for ori in aps.orientations:
                    ori.orientation = make_orientation_abs(obj_inst.pose.orientation, ori.orientation)

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
        # TODO to be used for parameters that are result of previous action(s)
        # ...there is no need to send parameters that are already in the project
        print_event(CurrentActionEvent(data=CurrentAction(action_id)))

    def parameters(self, action_id: str) -> Dict[str, Any]:

        try:
            act = self.project.action(action_id)
        except Arcor2Exception:
            raise ResourcesException("Action_id {} not found in project {}.".format(action_id, self.project.id))

        ret: Dict[str, Any] = {}

        for param in act.parameters:
            ret[param.id] = PARAM_PLUGINS[param.type].value(self.type_defs,
                                                            self.scene, self.project, action_id, param.id)

        return ret


T = TypeVar('T', bound=JsonSchemaMixin)


def lower(s: str) -> str:

    return s.lower()


class ResourcesBase(IntResources):

    def read_project_data(self, file_name: str, cls: Type[T]) -> T:

        try:

            with open(path.join("data", file_name + ".json")) as scene_file:

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
