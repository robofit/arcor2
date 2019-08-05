#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from typing import Dict, Union, Any
import importlib

from dataclasses_jsonschema import ValidationError
from pymongo import MongoClient  # type: ignore

from arcor2.helpers import convert_cc
from arcor2.object_types_utils import built_in_types_names
from arcor2.data import Project, Scene, ActionPoint
from arcor2.exceptions import ResourcesException
from arcor2.object_types import Generic
from arcor2.action import print_json


# TODO for bound methods - check whether provided action point belongs to the object


class IntResources:

    CUSTOM_OBJECT_TYPES_MODULE = "object_types"

    def __init__(self, scene: Scene, project: Project) -> None:

        self.scene = scene
        self.project = project

        self.objects: Dict[str, Generic] = {}

        built_in = built_in_types_names()

        for scene_obj in self.scene.objects:

            if scene_obj.type in built_in:
                module = importlib.import_module("arcor2.object_types." + convert_cc(scene_obj.type))
            else:
                module = importlib.import_module(IntResources.CUSTOM_OBJECT_TYPES_MODULE + "." +
                                                 convert_cc(scene_obj.type))

            cls = getattr(module, scene_obj.type)

            assert scene_obj.id not in self.objects, "Duplicate object id {}!".format(scene_obj.id)

            # TODO handle hierarchy of object_types (tree), e.g. call add_child...
            inst = cls(scene_obj.id, scene_obj.pose)
            self.objects[scene_obj.id] = inst

        # add action points to the object_types
        for project_obj in self.project.objects:

            for aps in project_obj.action_points:
                self.objects[project_obj.id].add_action_point(aps.id, aps.pose)

    @staticmethod
    def print_info(action_id: str, args: Dict[str, Any]) -> None:  # TODO dataclass for args
        """Helper method used to print out info about the action going to be executed."""

        print_json({"event": "currentAction", "data": {"action_id": action_id, "args": args}})

    def action_point(self, object_id: str, ap_id: str) -> ActionPoint:

        # TODO action point pose should be relative to its parent object pose - how and where to get the absolute pose?
        # ...temporarily, simply return action point as it is
        try:
            return self.objects[object_id].action_points[ap_id]
        except KeyError:
            raise ResourcesException("Unknown object id or action point id.")

    def parameters(self, action_id: str) -> Dict:

        for obj in self.project.objects:
            for aps in obj.action_points:
                for act in aps.actions:
                    if act.id == action_id:

                        ret: Dict[str, Union[str, float, ActionPoint]] = {}

                        for param in act.parameters:
                            if param.type == "ActionPoint":
                                assert isinstance(param.value, str)
                                object_id, ap_id = param.value.split('.')
                                ret[param.id] = self.action_point(object_id, ap_id)
                            else:
                                ret[param.id] = param.value

                        return ret

        raise ResourcesException("Action_id {} not found for project {}.".format(action_id, self.project.id))


class ResourcesBase(IntResources):
    """
    Wrapper around MongoDB document store API for specific project.
    """

    def __init__(self, project_id: str) -> None:

        client = MongoClient('localhost', 27017)

        proj_data: Union[None, Dict] = client.arcor2.projects.find_one({'id': project_id})

        if not proj_data:
            raise ResourcesException("Could not find project {}!".format(project_id))

        try:
            project: Project = Project.from_dict(proj_data)
        except ValidationError as e:
            raise ResourcesException("Invalid project: {}".format(e))

        scene_data: Union[None, Dict] = client.arcor2.scenes.find_one({'id': project.scene_id})

        if not scene_data:
            raise ResourcesException(f"Could not find scene "
                                     f"{project.scene_id} for project {project.id}!")

        try:
            scene: Scene = Scene.from_dict(scene_data)
        except ValidationError as e:
            raise ResourcesException("Invalid scene: {}".format(e))

        super(ResourcesBase, self).__init__(scene, project)
