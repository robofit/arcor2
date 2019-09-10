#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from typing import List, Any, Union, Iterator, Optional
from enum import Enum

from json import JSONEncoder
from dataclasses import dataclass, field

# latest release (with to_dict()) not yet available through pip, install it from git!
from dataclasses_jsonschema import JsonSchemaMixin


class ActionIOEnum(Enum):

    FIRST: str = "start"
    LAST: str = "end"


class ActionParameterTypeEnum(Enum):

    STRING: str = "string"
    DOUBLE: str = "double"
    ACTION_POINT: str = "ActionPoint"


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

    x: float
    y: float
    z: float


@dataclass
class Orientation(IterableIndexable):

    x: float
    y: float
    z: float
    w: float


@dataclass
class Pose(JsonSchemaMixin):

    position: Position
    orientation: Orientation


@dataclass
class ActionMetadata(JsonSchemaMixin):

    free: bool = False
    blocking: bool = False
    composite: bool = False
    blackbox: bool = False


@dataclass
class ActionPoint(JsonSchemaMixin):

    id: str
    pose: Pose


@dataclass
class SceneObject(JsonSchemaMixin):

    id: str
    type: str
    pose: Pose


@dataclass
class Scene(JsonSchemaMixin):

    id: str
    robot_system_id: str
    objects: List[SceneObject] = field(default_factory=list)
    desc: str = field(default_factory=str)


@dataclass
class ActionParameter(JsonSchemaMixin):

    id: str
    type: ActionParameterTypeEnum
    value: Union[float, str]


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
