#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from typing import Dict, Set, Tuple
from arcor2.exceptions import ResourcesException
from arcor2.data import Pose
from arcor2.object_types import Generic
from arcor2.object_types.utils import print_json
from pymongo import MongoClient  # type: ignore
import importlib
from arcor2.helpers import convert_cc, built_in_types_names

# TODO for bound methods - check whether provided action point belongs to the object


class ResourcesBase:
    """
    Wrapper around MongoDB document store API for specific project.
    """

    def __init__(self, project_id):

        self.project_id = project_id
        self.client = MongoClient('localhost', 27017)

        # TODO program should be parsed from script!
        self.program = self.client.arcor2.projects.find_one({'_id': project_id})

        if not self.program:
            raise ResourcesException("Could not find project {}!".format(project_id))

        # TODO switch to the "resource" format instead of server-ui format
        self.scene = self.client.arcor2.scenes.find_one({'_id': self.program["scene_id"]})

        if not self.scene:
            raise ResourcesException(f"Could not find scene "
                                     f"{self.program['scene_id']} for project {self.program['_id']}!")

        # TODO create instances of all object_types according to the scene
        self.objects: Dict[str, Generic] = {}

        built_in = built_in_types_names()

        for obj in self.scene["objects"]:

            if obj["type"] in built_in:
                module = importlib.import_module("arcor2.object_types." + convert_cc(obj["type"]))
            else:
                module = importlib.import_module("object_types." + convert_cc(obj["type"]))

            cls = getattr(module, obj["type"])

            assert obj["id"] not in self.objects, "Duplicate object id {}!".format(obj["id"])

            # TODO handle hierarchy of object_types (tree), e.g. call add_child...
            inst = cls(obj["id"],
                       Pose(list(obj["pose"]["position"].values()), list(obj["pose"]["orientation"].values())))
            self.objects[obj["id"]] = inst

        # add action points to the object_types
        for obj in self.program["objects"]:

            for aps in obj["action_points"]:
                self.objects[obj["id"]].add_action_point(aps["id"],
                                                         Pose(list(aps["pose"]["position"].values()),
                                                              list(aps["pose"]["orientation"].values())))

    @staticmethod
    def print_info(action_id: str, args: Dict) -> None:
        """Helper method used to print out info about the action going to be executed."""

        print_json({"event": "currentAction", "data": {"action_id": action_id, "args": args}})

    def action_ids(self) -> Set:

        ids: Set = set()

        for obj in self.program["objects"]:
            for aps in obj["action_points"]:
                for act in aps["actions"]:
                    assert act["id"] not in ids, "Action ID {} not globally unique.".format(act["id"])
                    ids.add(act["id"])

        return ids

    def action_point(self, object_id: str, ap_id: str) -> Tuple["Generic", str]:

        assert ap_id in self.objects[object_id].action_points

        # TODO action point pose should be relative to its parent object pose - how and where to get the absolute pose?
        # ...temporarily, simply return action point as it is
        return self.objects[object_id].action_points[ap_id]

    def parameters(self, action_id: str) -> Dict:

        for obj in self.program["objects"]:
            for aps in obj["action_points"]:
                for act in aps["actions"]:
                    if act["id"] == action_id:

                        ret = {}

                        for param in act["parameters"]:
                            if param["type"] == "ActionPoint":
                                object_id, ap_id = param["value"].split('.')
                                ret[param["id"]] = self.action_point(object_id, ap_id)
                            else:
                                ret[param["id"]] = param["value"]

                        return ret

        raise ResourcesException("Action_id {} not found for project {}.".format(action_id, self.project_id))
