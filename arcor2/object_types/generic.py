from typing import Optional, Dict, Set, FrozenSet

from arcor2.data.common import Pose, ActionPoint, ActionMetadata
from arcor2.exceptions import GenericException
from arcor2.action import action


class Generic:

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
        self._childs: Set[Generic] = set()

        self.action_points: Dict[str, ActionPoint] = {}

    def add_action_point(self, name: str, pose: Pose) -> None:

        self.action_points[name] = ActionPoint(name, pose)

    def add_child(self, obj: "Generic") -> None:

        if obj in self._childs:
            raise GenericException("Object {} already added as child.".format(obj))

        if self._child_limit is not None and len(self._childs) >= self._child_limit:
            raise GenericException("Child limit reached for {}.".format(self))

        self._childs.add(obj)

    def remove_child(self, obj: "Generic") -> None:

        try:
            self._childs.remove(obj)
        except KeyError:
            raise GenericException("Object {} not found.".format(obj))

    def childs(self) -> FrozenSet["Generic"]:

        return frozenset(self._childs)

    def __repr__(self) -> str:
        return str(self.__dict__)

    @action
    def nop(self) -> None:
        pass

    nop.__action__ = ActionMetadata()  # type: ignore
