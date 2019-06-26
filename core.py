#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from typing import Optional, Collection, Dict, Hashable, Union, Callable, Set, FrozenSet, List
from arcor2.exceptions import WorldObjectException, RobotException, ResourcesException
from arcor2.data import Pose, ActionPoint, ActionMetadata
from pymongo import MongoClient

# TODO for bound methods - check whether provided action point belongs to the object


class Resources:
    """
    Wrapper around MongoDB document store API for specific project.
    """

    def __init__(self, project_id):

        self.project_id = project_id
        self.client = MongoClient('localhost', 27017)

        # TODO program should be parsed from script!
        self.program = self.client.arcor2.projects.find_one({'project_id': project_id})

        # TODO switch to the "resource" format instead of server-ui format
        self.scene = self.client.arcor2.scenes.find_one({'scene_id': self.program["scene_id"]})

    def action_ids(self) -> Set:

        ids = set()

        for obj in self.program["objects"]:
            for aps in obj["action_points"]:
                for act in aps["actions"]:
                    assert act["id"] not in ids, "Action ID {} not globally unique.".format(act["id"])
                    ids.add(act["id"])

        return ids

    def action_point(self, object_id: str, ap_id: str) -> ActionPoint:

        for obj in self.program["objects"]:

            if obj["id"] != object_id:
                continue

            for aps in obj["action_points"]:

                if aps["id"] != ap_id:
                    continue

                return ActionPoint(ap_id, Pose(aps["position"].values(), aps["orientation"].values()))

        raise ResourcesException("Could not find action point {} for object {}.".format(ap_id, object_id))

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

        self.action_points[name] = ActionPoint(name, self, pose)

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

    def __init__(self, end_effectors: Collection[Hashable]) -> None:  # TODO pose

        super(Robot, self).__init__(child_limit=len(end_effectors))

    def move_to(self, action_point: ActionPoint, end_effector: str) -> None:
        """

        Parameters
        ----------
        end_effector:
            Robot's end effector.
        action_point:
            Move specified end-effector to the given pose.
        """

        # TODO call underlying API
        return

    move_to.__action__ = ActionMetadata(free=True, blocking=True)
