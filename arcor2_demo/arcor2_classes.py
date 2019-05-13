#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from typing import Optional, Iterable, Dict, Tuple, List
import time


class Arcor2Exception(Exception):
    pass


class Pose(object):

    def __init__(self, position: Iterable[float] = (
            0, 0, 0), orientation: Iterable[float] = (0, 0, 0, 1)):

        self.position = position
        self.orientation = orientation


class WorldObjectException(Exception):
    pass


class WorldObject(object):

    def __init__(self, pose: Optional[Pose] = None,
                 child_limit: Optional[int] = None):

        self.pose = pose
        self._child_limit = child_limit
        self._contains: List[WorldObject] = []

    def add_child(self, obj: "WorldObject"):

        assert obj not in self._contains
        assert self._child_limit is None or len(
            self._contains) < self._child_limit

        self._contains.append(obj)

    def remove_child(self, obj: "WorldObject"):

        self._contains.remove(obj)

    def childs(self) -> Tuple["WorldObject", ...]:

        return tuple(self._contains)


class Robot(object):
    """
    Abstract class representing robot and its basic capabilities (motion)
    """

    def __init__(self):

        self.holding: Dict[int, WorldObject] = {}

    def move_to(self, pose: Pose) -> None:
        time.sleep(1)

    def pick(self, obj: WorldObject, end_effector: int):
        self.holding[end_effector] = obj
        # TODO set obj.pose relative to the gripper now?

    def place_to(self, pose: Pose, end_effector: int) -> WorldObject:
        obj = self.holding[end_effector]
        del self.holding[end_effector]
        return obj
