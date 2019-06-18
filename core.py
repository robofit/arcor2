#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from typing import Optional, Collection, Dict, Hashable, Union, Callable, Set, FrozenSet, cast, List, Tuple
import time
from arcor2.exceptions import WorldObjectException, RobotException
from arcor2.data import Pose, Instructions, ActionPoint


WoAp = Tuple[str, Optional["WorldObject"]]


class WorldObject:

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
        self.instructions: Instructions = Instructions()

        # TODO get it from resources
        self.action_points: Dict[str, ActionPoint] = {}

    def add_action_point(self, ap: ActionPoint):

        self.action_points[ap.name] = ap

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

    def _check_action_point_arg(self, arg: WoAp, method: Callable) -> None:
        """
        Free methods may be used with action point(s) from another WorldObject.
        In that case, reference to the action point's parent object has to be given.

        Parameters
        ----------
        arg
        method

        Returns
        -------

        """

        assert (method in self.instructions.bound and len(arg) == 1) or \
               (method in self.instructions.free and len(arg) == 2)


class Workspace(WorldObject):
    pass


class Robot(WorldObject):
    """
    Abstract class representing robot and its basic capabilities (motion)
    """

    def __init__(self, end_effectors: Collection[Hashable]) -> None:  # TODO pose

        super(Robot, self).__init__(child_limit=len(end_effectors))

        self._holding: Dict[Hashable, Union[WorldObject, None]] = {}  # TODO partial duplication of child mechanism?

        for end_effector in end_effectors:
            self._holding[end_effector] = None

        for inst in (self.move_to, self.pick, self.place_to):

            self.instructions.blocking.add(inst)
            self.instructions.free.add(inst)

    def holding(self, end_effector: Hashable) -> Union[None, WorldObject]:
        """Allows to test if robot holds something.

        Parameters
        ----------
        end_effector:
            Identificator for the end effector.

        """

        try:
            return self._holding[end_effector]
        except KeyError:
            return None

    def move_to(self, target: WoAp, end_effector: Hashable) -> None:
        """

        Parameters
        ----------
        end_effector:
            Robot's end effector.
        target:
            Move specified end-effector to the given pose.
        """

        self._check_action_point_arg(target, self.move_to)

        time.sleep(1)

    def pick(self, pre_grasp: WoAp, obj: WorldObject, end_effector: Hashable) -> None:
        """Picks given object from its pose using a given end effector.

        The object has to know its pose.

        Parameters
        ----------
        action_point:
            Pre-grasp pose.
        obj:
            Object to be picked.
        end_effector:
            End effector.

        Raises
        -------
        RobotException
            When something goes wrong.

        """

        self._check_action_point_arg(pre_grasp, self.pick)

        if obj.pose is None:
            raise RobotException("Object {} has no pose set.".format(obj))

        if end_effector in self._holding:
            raise RobotException("End effector {} already holds object.".format(end_effector))

        self._holding[end_effector] = obj
        # TODO set obj.pose relative to the gripper now?

    def place_to(self, where: WoAp, end_effector: Hashable) -> WorldObject:
        """

        Parameters
        ----------
        pose:
            Pose where to place the object.
        end_effector
            Specifies end effector to use (robot might hold more objects using different end effectors).

        Returns
        -------
        The placed object.

        """

        self._check_action_point_arg(where, self.place_to)

        try:
            if self._holding[end_effector] is None:
                raise RobotException("Robot's end-effector {} does not hold any object.".format(end_effector))
        except KeyError:
            raise RobotException("Unknown end-effector!")

        obj = self._holding[end_effector]
        self._holding[end_effector] = None
        return cast(WorldObject, obj)
