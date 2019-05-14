#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from typing import Optional, Iterable, Dict, Tuple, List
import time


class Arcor2Exception(Exception):
    pass


class Pose(object):

    def __init__(self, position: Iterable[float] = (
            0, 0, 0), orientation: Iterable[float] = (0, 0, 0, 1)):

        assert len(position) == 3 and len(orientation) == 4

        self.position = position
        self.orientation = orientation


class WorldObjectException(Arcor2Exception):
    pass


class WorldObject(object):

    def __init__(self, pose: Optional[Pose] = None,
                 child_limit: Optional[int] = None):

        self.pose = pose
        self._child_limit = child_limit
        self._contains: List[WorldObject] = []

    def add_child(self, obj: "WorldObject"):

        if obj in self._contains:
            raise WorldObjectException(
                "Object {} already added as child.".format(obj))

        if self._child_limit is not None and len(
                self._contains) >= self._child_limit:
            raise WorldObjectException("Child limit reached.")

        self._contains.append(obj)

    def remove_child(self, obj: "WorldObject"):

        try:
            self._contains.remove(obj)
        except ValueError:
            raise WorldObjectException("Object {} not found.".format(obj))

    def childs(self) -> Tuple["WorldObject", ...]:

        return tuple(self._contains)


class RobotException(Arcor2Exception):
    pass


class Robot(object):
    """
    Abstract class representing robot and its basic capabilities (motion)
    """

    def __init__(self):

        self._holding: Dict[int, WorldObject] = {}

    def move_to(self, pose: Pose) -> None:
        time.sleep(1)

    def pick(self, obj: WorldObject, end_effector: int):

        if obj.pose is None:
            raise RobotException("Object {} has no pose set.".format(obj))

        if end_effector in self._holding:
            raise RobotException(
                "End effector {} already holds object.".format(end_effector))

        self._holding[end_effector] = obj
        # TODO set obj.pose relative to the gripper now?

    def place_to(self, pose: Pose, end_effector: int) -> WorldObject:

        try:
            obj = self._holding[end_effector]
        except KeyError:
            raise RobotException(
                "Robot's end-effector {} does not hold any object.".format(end_effector))

        try:
            del self._holding[end_effector]
        except KeyError:
            pass

        return obj
