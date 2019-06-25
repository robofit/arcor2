#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from typing import Optional, Collection, Dict, Hashable, Union, Callable, Set, FrozenSet
from arcor2.exceptions import WorldObjectException, RobotException
from arcor2.data import Pose, ActionPoint, ActionMetadata

# TODO for bound methods - check whether provided action point belongs to the object


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

        for end_effector in end_effectors:
            self._holding[end_effector] = None

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
