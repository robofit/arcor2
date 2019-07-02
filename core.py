#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from typing import Optional, Dict, Set, FrozenSet, Tuple, Union
from arcor2.exceptions import WorldObjectException, ResourcesException
from arcor2.data import Pose, ActionPoint, ActionMetadata, DataClassEncoder
from pymongo import MongoClient
import importlib
import json
import time
import sys
import select  # only available on Linux?

# TODO for bound methods - check whether provided action point belongs to the object


def read_stdin(timeout=0.0) -> Union[str, None]:

    if select.select([sys.stdin], [], [], timeout)[0]:
        return sys.stdin.readline().strip()
    return None


def handle_action(obj_id, f, where) -> None:

    d = {"event": "actionState", "data": {"method": "{}/{}".format(obj_id, f.__name__), "where": where}}
    print_json(d)

    ctrl_cmd = read_stdin()

    if ctrl_cmd == "p":
        print_json({"event": "projectState", "data": {"state": "paused"}})
        while True:
            ctrl_cmd = read_stdin(0.1)
            if ctrl_cmd == "r":
                print_json({"event": "projectState", "data": {"state": "resumed"}})
                break


def print_json(d: Dict) -> None:

    print(json.dumps(d, cls=DataClassEncoder))
    sys.stdout.flush()


def action(f):  # TODO read stdin and pause if requested
    def wrapper(*args, **kwargs):

        handle_action(args[0].name, f, "before")
        res = f(*args, **kwargs)
        handle_action(args[0].name, f, "after")
        return res

    return wrapper


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
            raise ResourcesException("Could not find scene {} for project {}!".format(self.program["scene_id"], self.program["_id"]))

        # TODO create instances of all objects according to the scene
        self.objects: Dict[str, WorldObject] = {}

        for obj in self.scene["objects"]:

            try:
                module_name, cls_name = obj["type"].split('/')
            except ValueError:
                raise ResourcesException("Invalid object type {}, should be in format 'python_module/class'.".format(obj["type"]))

            module = importlib.import_module(module_name)
            cls = getattr(module, cls_name)

            assert obj["id"] not in self.objects, "Duplicate object id {}!".format(obj["id"])

            # TODO handle hierarchy of objects (tree), e.g. call add_child...
            inst = cls(obj["id"], Pose(list(obj["position"].values()), list(obj["orientation"].values())))
            self.objects[obj["id"]] = inst

        # add action points to the objects
        for obj in self.program["objects"]:

            for aps in obj["action_points"]:
                self.objects[obj["id"]].add_action_point(aps["id"], Pose(list(aps["position"].values()), list(aps["orientation"].values())))

    @staticmethod
    def print_info(action_id: str, args: Dict) -> None:

        print_json({"event": "currentAction", "data": {"action_id": action_id, "args": args}})

    def action_ids(self) -> Set:

        ids: Set = set()

        for obj in self.program["objects"]:
            for aps in obj["action_points"]:
                for act in aps["actions"]:
                    assert act["id"] not in ids, "Action ID {} not globally unique.".format(act["id"])
                    ids.add(act["id"])

        return ids

    def action_point(self, object_id: str, ap_id: str) -> Tuple["WorldObject", str]:

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


class WorldObject:

    __DESCRIPTION__ = "Generic object"

    def __init__(self, name: Optional[str] = None,
                 pose: Optional[Pose] = None,
                 child_limit: Optional[int] = None) -> None:

        if name is None:
            self.name = type(self).__name__
        else:
            self.name = name

        self.pose = pose
        self._child_limit = child_limit
        self._childs: Set[WorldObject] = set()

        # TODO get it from resources
        self.action_points: Dict[str, ActionPoint] = {}

    def add_action_point(self, name: str, pose: Pose) -> None:

        self.action_points[name] = ActionPoint(name, pose)

    def add_child(self, obj: "WorldObject") -> None:

        if obj in self._childs:
            raise WorldObjectException("Object {} already added as child.".format(obj))

        if self._child_limit is not None and len(self._childs) >= self._child_limit:
            raise WorldObjectException("Child limit reached for {}.".format(self))

        self._childs.add(obj)

    def remove_child(self, obj: "WorldObject") -> None:

        try:
            self._childs.remove(obj)
        except KeyError:
            raise WorldObjectException("Object {} not found.".format(obj))

    def childs(self) -> FrozenSet["WorldObject"]:

        return frozenset(self._childs)

    def __repr__(self):
        return str(self.__dict__)


class Workspace(WorldObject):
    pass


class Robot(WorldObject):
    """
    Abstract class representing robot and its basic capabilities (motion)
    """

    @action
    def move_to(self, target: ActionPoint, end_effector: str, speed: int) -> None:

        # TODO action point pose should be relative to its parent object pose - how and where to get the absolute pose?

        # TODO call underlying API
        time.sleep(1)
        return

    move_to.__action__ = ActionMetadata("Move", free=True, blocking=True)
