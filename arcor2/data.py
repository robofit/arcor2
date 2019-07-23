#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from typing import List, Any, Union
from json import JSONEncoder
from dataclasses import dataclass, field

# latest release (with to_dict()) not yet available through pip, install it from git!
from dataclasses_jsonschema import JsonSchemaMixin


class ActionIOEnum:

    FIRST: str = "start"
    LAST: str = "end"


class DataClassEncoder(JSONEncoder):

    def default(self, o: Any) -> Any:

        if isinstance(o, JsonSchemaMixin):
            return o.to_dict()

        return super().default(o)


@dataclass
class Position(JsonSchemaMixin):

    x: float
    y: float
    z: float

    def to_list(self) -> List:

        return [self.x, self.y, self.z]


@dataclass
class Orientation(JsonSchemaMixin):

    x: float
    y: float
    z: float
    w: float

    def to_list(self) -> List:

        return [self.x, self.y, self.z, self.w]


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
    objects: List[SceneObject] = field(default_factory=list)


@dataclass
class ActionParameter(JsonSchemaMixin):

    id: str
    type: str
    value: Union[str, float]


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


@dataclass
class ObjectType(JsonSchemaMixin):

    type: str
    description: str = field(default_factory=str)
    built_in: bool = False
    base: str = field(default_factory=str)


@dataclass
class ObjectActionArgs(JsonSchemaMixin):

    name: str
    type: str


@dataclass
class ObjectAction(JsonSchemaMixin):

    name: str
    action_args: List[ObjectActionArgs] = field(default_factory=list)
    returns: str = "NoneType"
    origins: str = ""
    meta: ActionMetadata = field(default_factory=ActionMetadata)


ObjectActions = List[ObjectAction]
