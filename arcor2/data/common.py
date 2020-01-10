#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from typing import List, Any, Iterator, Optional, Tuple, Set, Dict, Union
from enum import Enum, unique

from json import JSONEncoder
from dataclasses import dataclass, field

import numpy as np  # type: ignore
import quaternion  # type: ignore

from dataclasses_jsonschema import JsonSchemaMixin

from arcor2.exceptions import Arcor2Exception


@unique
class StrEnum(str, Enum):

    @classmethod
    def set(cls) -> Set[str]:
        return set(map(lambda c: c.value, cls))  # type: ignore


@unique
class IntEnum(int, Enum):

    @classmethod
    def set(cls) -> Set[int]:
        return set(map(lambda c: c.value, cls))  # type: ignore


class ActionIOEnum(StrEnum):

    FIRST: str = "start"
    LAST: str = "end"


class DataClassEncoder(JSONEncoder):

    def default(self, o: Any) -> Any:

        if isinstance(o, JsonSchemaMixin):
            return o.to_dict()

        return super().default(o)


@dataclass
class IterableIndexable(JsonSchemaMixin):

    def __getitem__(self, item: int) -> float:

        attr = getattr(self, tuple(self.__dict__.keys())[item])
        assert isinstance(attr, float)
        return attr

    def __iter__(self) -> Iterator[float]:

        yield from self.__dict__.values()


@dataclass
class Position(IterableIndexable):

    x: float = 0.0
    y: float = 0.0
    z: float = 0.0


@dataclass
class Orientation(IterableIndexable):

    x: float = 0.0
    y: float = 0.0
    z: float = 0.0
    w: float = 1.0

    def as_quaternion(self) -> quaternion.quaternion:

        return np.quaternion(self.x, self.y, self.z, self.w)

    def set_from_quaternion(self, q: quaternion.quaternion) -> None:

        arr = quaternion.as_float_array(q)
        self.x = arr[0]
        self.y = arr[1]
        self.z = arr[2]
        self.w = arr[3]


@dataclass
class NamedOrientation(JsonSchemaMixin):

    id: str
    orientation: Orientation


@dataclass
class Pose(JsonSchemaMixin):

    position: Position = field(default_factory=Position)
    orientation: Orientation = field(default_factory=Orientation)


@dataclass
class ActionMetadata(JsonSchemaMixin):

    free: bool = False
    blocking: bool = False
    composite: bool = False
    blackbox: bool = False


@dataclass
class Joint(JsonSchemaMixin):

    name: str
    rotation: float


@dataclass
class RobotJoints(JsonSchemaMixin):

    id: str
    robot_id: str
    joints: List[Joint]
    is_valid: bool = False


@dataclass
class ActionPoint(JsonSchemaMixin):

    id: str
    position: Position
    orientations: List[NamedOrientation] = field(default_factory=list)
    robot_joints: List[RobotJoints] = field(default_factory=list)

    def pose(self, orientation_id: str) -> Pose:

        for ori in self.orientations:
            if ori.id == orientation_id:
                return Pose(self.position, ori.orientation)
        raise Arcor2Exception(f"Action point {self.id} does not contain orientation {orientation_id}.")

    def get_joints(self, robot_id: str, joints_id: str) -> RobotJoints:

        for joints in self.robot_joints:
            if joints.id == joints_id and robot_id == joints.robot_id:
                return joints
        raise Arcor2Exception(f"Action point {self.id} does not contain robot joints {joints_id}.")


@dataclass
class SceneObject(JsonSchemaMixin):

    id: str
    type: str
    pose: Pose


@dataclass
class SceneService(JsonSchemaMixin):

    type: str
    configuration_id: str


@dataclass
class Scene(JsonSchemaMixin):

    id: str
    objects: List[SceneObject] = field(default_factory=list)
    services: List[SceneService] = field(default_factory=list)
    desc: str = field(default_factory=str)

    def __post_init__(self):

        self._id_cache: Dict[str, Union[SceneObject, SceneService]] = {}

    def object_or_service(self, object_or_service_id: str) -> Union[SceneObject, SceneService]:

        if not self._id_cache:
            for obj in self.objects:
                self._id_cache[obj.id] = obj
            for srv in self.services:
                self._id_cache[srv.type] = srv

        try:
            return self._id_cache[object_or_service_id]
        except KeyError:
            raise Arcor2Exception(f"Unknown object/service id: {object_or_service_id}, "
                                  f"known are: {self._id_cache.keys()}")  # TODO DataException?


@dataclass
class IdValue(JsonSchemaMixin):

    id: str
    value: Any


class ActionParameterException(Arcor2Exception):
    pass


@dataclass
class ActionParameter(IdValue):

    type: str


@dataclass
class ActionIO(JsonSchemaMixin):

    default: str


@dataclass
class Action(JsonSchemaMixin):

    id: str
    type: str
    parameters: List[ActionParameter] = field(default_factory=list)
    inputs: List[ActionIO] = field(default_factory=list)
    outputs: List[ActionIO] = field(default_factory=list)

    def parse_type(self) -> Tuple[str, str]:

        try:
            obj_id, action = self.type.split("/")
        except ValueError:
            raise Arcor2Exception(f"Action: {self.id} has invalid type: {self.type}.")
        return obj_id, action

    def parameter(self, parameter_id) -> ActionParameter:

        for param in self.parameters:
            if parameter_id == param.id:
                return param

        raise Arcor2Exception("Param not found")


@dataclass
class ProjectActionPoint(ActionPoint):

    actions: List[Action] = field(default_factory=list)


@dataclass
class ProjectObject(JsonSchemaMixin):

    id: str
    action_points: List[ProjectActionPoint] = field(default_factory=list)


@dataclass
class Project(JsonSchemaMixin):

    id: str
    scene_id: str
    objects: List[ProjectObject] = field(default_factory=list)
    desc: str = field(default_factory=str)
    has_logic: bool = True

    def __post_init__(self):

        self._action_cache: Dict[str, Action] = {}
        self._ap_cache: Dict[str, ActionPoint] = {}

    def _build_cache(self):

        for obj in self.objects:
            for aps in obj.action_points:
                assert aps.id not in self._ap_cache, "Action point ID not unique."
                self._ap_cache[aps.id] = aps
                for act in aps.actions:
                    self._action_cache[act.id] = act

    def invalidate_cache(self):

        self._action_cache.clear()
        self._ap_cache.clear()

    def action(self, action_id: str) -> Action:

        if not self._action_cache:
            self._build_cache()

        try:
            return self._action_cache[action_id]
        except KeyError:
            raise Arcor2Exception("Action not found")

    def action_point(self, action_point_id: str) -> ActionPoint:

        if not self._ap_cache:
            self._build_cache()

        try:
            return self._ap_cache[action_point_id]
        except KeyError:
            raise Arcor2Exception("Action point not found")


@dataclass
class ProjectSources(JsonSchemaMixin):

    id: str  # project_id
    resources: str
    script: str


@dataclass
class IdDesc(JsonSchemaMixin):
    id: str
    desc: Optional[str] = None


@dataclass
class IdDescList(JsonSchemaMixin):

    items: List[IdDesc] = field(default_factory=list)


class ProjectStateEnum(Enum):

    RUNNING: str = "running"
    STOPPED: str = "stopped"
    PAUSED: str = "paused"
    RESUMED: str = "resumed"


class ActionStateEnum(Enum):

    BEFORE: str = "before"
    AFTER: str = "after"


@dataclass
class ActionState(JsonSchemaMixin):

    object_id: str = ""
    method: str = ""
    where: ActionStateEnum = ActionStateEnum.BEFORE


@dataclass
class ProjectState(JsonSchemaMixin):

    state: ProjectStateEnum = ProjectStateEnum.STOPPED


@dataclass
class CurrentAction(JsonSchemaMixin):

    action_id: str = ""
    args: List[ActionParameter] = field(default_factory=list)
