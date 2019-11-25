#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from typing import List, Any, Iterator, Optional, Union, Tuple, Set
from enum import Enum

from json import JSONEncoder
from dataclasses import dataclass, field

import numpy as np  # type: ignore
import quaternion  # type: ignore

from dataclasses_jsonschema import JsonSchemaMixin

from arcor2.exceptions import Arcor2Exception


class Arcor2Enum(Enum):

    @classmethod
    def set(cls) -> Set[str]:
        return set(map(lambda c: c.value, cls))  # type: ignore


class ActionIOEnum(Arcor2Enum):

    FIRST: str = "start"
    LAST: str = "end"


class ActionParameterTypeEnum(Enum):

    STRING: str = "string"
    DOUBLE: str = "double"
    INTEGER: str = "integer"
    ACTION_POINT: str = "ActionPoint"
    ENUM: str = "enum"


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

    x: float = 0
    y: float = 0
    z: float = 0


@dataclass
class Orientation(IterableIndexable):

    x: float = 0
    y: float = 0
    z: float = 0
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

    robot_id: str = ""
    joints: List[Joint] = field(default_factory=list)


@dataclass
class ActionPoint(JsonSchemaMixin):

    id: str
    pose: Pose

    # TODO store joints in project variable instead
    joints: Optional[RobotJoints] = field(default_factory=RobotJoints)


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


@dataclass
class IdValue(JsonSchemaMixin):

    id: str
    value: Any


@dataclass
class ActionParameter(IdValue):

    type: ActionParameterTypeEnum

    def __post_init__(self) -> None:
        # TODO implement value type check
        pass

    def parse_value(self) -> Tuple[str, str]:

        assert self.type == ActionParameterTypeEnum.ACTION_POINT

        try:
            obj_id, ap_id = self.type.value.split(".")
        except ValueError:
            raise Arcor2Exception(f"Parameter: {self.id} has invalid value: {self.value}.")
        return obj_id, ap_id


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


SUPPORTED_ARGS = Union[str, float, int, ActionPoint]

ARGS_MAPPING = {
    str: ActionParameterTypeEnum.STRING,
    float: ActionParameterTypeEnum.DOUBLE,
    int: ActionParameterTypeEnum.INTEGER,
    ActionPoint: ActionParameterTypeEnum.ACTION_POINT
}


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
