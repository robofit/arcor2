#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from typing import Optional, Collection, Dict, Tuple, List, Hashable, Union
import time


class Arcor2Exception(Exception):
    pass


class Pose:

    def __init__(self, position: Collection[float] = (
            0, 0, 0), orientation: Collection[float] = (0, 0, 0, 1)) -> None:

        assert len(position) == 3 and len(orientation) == 4

        self.position = position
        self.orientation = orientation


class WorldObjectException(Arcor2Exception):
    pass


class WorldObject:

    def __init__(self, pose: Optional[Pose] = None,
                 child_limit: Optional[int] = None) -> None:

        self.pose = pose
        self._child_limit = child_limit
        self._contains: List[WorldObject] = []

    def add_child(self, obj: "WorldObject") -> None:

        if obj in self._contains:
            raise WorldObjectException(
                "Object {} already added as child.".format(obj))

        if self._child_limit is not None and len(
                self._contains) >= self._child_limit:
            raise WorldObjectException(
                "Child limit reached for {}.".format(self))

        self._contains.append(obj)

    def remove_child(self, obj: "WorldObject") -> None:

        try:
            self._contains.remove(obj)
        except ValueError:
            raise WorldObjectException("Object {} not found.".format(obj))

    def childs(self) -> Tuple["WorldObject", ...]:

        return tuple(self._contains)


class RobotException(Arcor2Exception):
    pass


class Robot:
    """
    Abstract class representing robot and its basic capabilities (motion)
    """

    def __init__(self) -> None:

        self._holding: Dict[Hashable, WorldObject] = {}

    def holding(self, end_effector: Hashable) -> Union[None, WorldObject]:

        try:
            return self._holding[end_effector]
        except KeyError:
            return None

    def move_to(self, pose: Pose) -> None:
        time.sleep(1)

    def pick(self, obj: WorldObject, end_effector: int) -> None:

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
