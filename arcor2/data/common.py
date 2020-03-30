#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, unique
from json import JSONEncoder
from typing import List, Any, Iterator, Optional, Tuple, Set, Dict, Union

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
    user_id: str
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
    value: float


@dataclass
class ProjectRobotJoints(JsonSchemaMixin):

    id: str
    user_id: str
    robot_id: str
    joints: List[Joint]
    is_valid: bool = False


@dataclass
class ActionPoint(JsonSchemaMixin):

    id: str
    user_id: str
    position: Position
    parent: Optional[str] = None
    orientations: List[NamedOrientation] = field(default_factory=list)
    robot_joints: List[ProjectRobotJoints] = field(default_factory=list)

    def pose(self, orientation_id: str = "default") -> Pose:

        for ori in self.orientations:
            if ori.id == orientation_id:
                return Pose(self.position, ori.orientation)
        raise Arcor2Exception(f"Action point {self.id} does not contain orientation {orientation_id}.")

    def get_joints(self, robot_id: str, joints_id: str) -> ProjectRobotJoints:

        for joints in self.robot_joints:
            if joints.id == joints_id and robot_id == joints.robot_id:
                return joints
        raise Arcor2Exception(f"Action point {self.id} does not contain robot joints {joints_id}.")


@dataclass
class SceneObject(JsonSchemaMixin):

    id: str
    user_id: str
    type: str
    pose: Pose


@dataclass
class SceneService(JsonSchemaMixin):

    type: str
    configuration_id: str


@dataclass
class Scene(JsonSchemaMixin):

    id: str
    user_id: str
    objects: List[SceneObject] = field(default_factory=list)
    services: List[SceneService] = field(default_factory=list)
    desc: str = field(default_factory=str)
    last_modified: Optional[datetime] = None

    def object(self, object_id: str) -> SceneObject:

        for obj in self.objects:
            if obj.id == object_id:
                return obj
        raise Arcor2Exception(f"Object ID {object_id} not found.")

    def service(self, service_type: str) -> SceneService:

        for srv in self.services:
            if srv.type == service_type:
                return srv
        raise Arcor2Exception(f"Service of type {service_type} not found.")

    def object_or_service(self, object_or_service_id: str) -> Union[SceneObject, SceneService]:

        try:
            return self.object(object_or_service_id)
        except Arcor2Exception:
            pass

        try:
            return self.service(object_or_service_id)
        except Arcor2Exception:
            pass

        raise Arcor2Exception(f"Scene does not contain object/service with id '{object_or_service_id}'.")


@dataclass
class IdValue(JsonSchemaMixin):

    id: str
    value: str


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
    user_id: str
    type: str
    parameters: List[ActionParameter] = field(default_factory=list)
    inputs: List[ActionIO] = field(default_factory=list)
    outputs: List[ActionIO] = field(default_factory=list)

    def parse_type(self) -> Tuple[str, str]:

        try:
            obj_id_str, action = self.type.split("/")
        except ValueError:
            raise Arcor2Exception(f"Action: {self.id} has invalid type: {self.type}.")
        return obj_id_str, action

    def parameter(self, parameter_id) -> ActionParameter:

        for param in self.parameters:
            if parameter_id == param.id:
                return param

        raise Arcor2Exception("Param not found")


@dataclass
class ProjectActionPoint(ActionPoint):

    actions: List[Action] = field(default_factory=list)


@dataclass
class Project(JsonSchemaMixin):

    id: str
    user_id: str
    scene_id: str
    action_points: List[ProjectActionPoint] = field(default_factory=list)
    desc: str = field(default_factory=str)
    has_logic: bool = True
    last_modified: Optional[datetime] = None

    @property
    def action_points_with_parent(self) -> List[ProjectActionPoint]:
        """
        Get action points which are relative to something (parent is set).
        :return:
        """

        return [ap for ap in self.action_points if ap.parent]

    @property
    def action_points_user_ids(self) -> Set[str]:
        return {ap.user_id for ap in self.action_points}

    def action(self, action_id: str) -> Action:

        for ap in self.action_points:
            for ac in ap.actions:
                if ac.id == action_id:
                    return ac
        else:
            raise Arcor2Exception("Action not found")

    def action_point(self, action_point_id: str) -> ActionPoint:

        for ap in self.action_points:
            if ap.id == action_point_id:
                return ap
        else:
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


@dataclass
class BroadcastInfo(JsonSchemaMixin):

    host: str
    port: int
