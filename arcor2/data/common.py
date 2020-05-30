#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum, unique
from json import JSONEncoder
from typing import List, Any, Iterator, Optional, Tuple, Set, Union
import uuid

import quaternion  # type: ignore
from dataclasses_jsonschema import JsonSchemaMixin

from arcor2.exceptions import Arcor2Exception


def uid() -> str:
    return uuid.uuid4().hex


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

    def rotated(self, rot: "Orientation", inverse: bool = False) -> "Position":

        q = rot.as_quaternion()

        if inverse:
            q = q.inverse()

        rotated_vector = quaternion.rotate_vectors([q], [list(self)])[0][0]
        return Position(rotated_vector[0], rotated_vector[1], rotated_vector[2])


@dataclass
class Orientation(IterableIndexable):

    x: float = 0.0
    y: float = 0.0
    z: float = 0.0
    w: float = 1.0

    def as_quaternion(self) -> quaternion.quaternion:
        return quaternion.quaternion(self.w, self.x, self.y, self.z).normalized()

    def set_from_quaternion(self, q: quaternion.quaternion) -> None:

        nq = q.normalized()

        self.x = nq.x
        self.y = nq.y
        self.z = nq.z
        self.w = nq.w

    def __eq__(self, other) -> bool:

        if not isinstance(other, Orientation):
            return False

        return quaternion.isclose(self.as_quaternion(), other.as_quaternion(), rtol=1.e-8)[0]


@dataclass
class NamedOrientation(JsonSchemaMixin):

    id: str
    name: str
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
    cancellable: bool = field(init=False, default=False)


@dataclass
class Joint(JsonSchemaMixin):

    name: str
    value: float


@dataclass
class ProjectRobotJoints(JsonSchemaMixin):

    id: str
    name: str
    robot_id: str
    joints: List[Joint]
    is_valid: bool = False


@dataclass
class ActionPoint(JsonSchemaMixin):

    id: str
    name: str
    position: Position
    parent: Optional[str] = None
    orientations: List[NamedOrientation] = field(default_factory=list)
    robot_joints: List[ProjectRobotJoints] = field(default_factory=list)

    def pose(self, orientation_id: str = "default") -> Pose:

        for ori in self.orientations:
            if ori.id == orientation_id:
                return Pose(self.position, ori.orientation)
        raise Arcor2Exception(f"Action point {self.id} does not contain orientation {orientation_id}.")

    def orientation(self, orientation_id: str) -> NamedOrientation:

        for ori in self.orientations:
            if ori.id == orientation_id:
                return ori
        raise Arcor2Exception(f"Action point {self.id} does not contain orientation {orientation_id}.")

    def joints(self, joints_id: str) -> ProjectRobotJoints:

        for joints in self.robot_joints:
            if joints.id == joints_id:
                return joints
        raise Arcor2Exception(f"Action point {self.id} does not contain robot joints {joints_id}.")

    def orientation_names(self) -> Set[str]:
        return {ori.name for ori in self.orientations}

    def joints_names(self) -> Set[str]:
        return {joints.name for joints in self.robot_joints}

    def joints_for_robot(self, robot_id: str, joints_id: str) -> ProjectRobotJoints:

        joints = self.joints(joints_id)

        if joints.robot_id != robot_id:
            raise Arcor2Exception("Joints for a different robot.")

        return joints

    def invalidate_joints(self):

        for joints in self.robot_joints:
            joints.is_valid = False


@dataclass
class SceneObject(JsonSchemaMixin):

    id: str
    name: str
    type: str
    pose: Pose


@dataclass
class SceneService(JsonSchemaMixin):

    type: str
    configuration_id: str


@dataclass
class Scene(JsonSchemaMixin):

    id: str
    name: str
    objects: List[SceneObject] = field(default_factory=list)
    services: List[SceneService] = field(default_factory=list)
    desc: str = field(default_factory=str)
    modified: Optional[datetime] = None
    int_modified: Optional[datetime] = None

    def bare(self) -> "Scene":
        return Scene(self.id, self.name, desc=self.desc)

    def update_modified(self):
        self.int_modified = datetime.now(tz=timezone.utc)

    def has_changes(self) -> bool:

        if self.int_modified is None:
            return False

        if self.modified is None:
            return True

        return self.int_modified > self.modified

    def object_names(self) -> Iterator[str]:

        for obj in self.objects:
            yield obj.name

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
    name: str
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

    def bare(self) -> "Action":
        return Action(self.id, self.name, self.type)


@dataclass
class ProjectActionPoint(ActionPoint):

    actions: List[Action] = field(default_factory=list)

    def bare(self) -> "ProjectActionPoint":
        return ProjectActionPoint(self.id, self.name, self.position, self.parent)


@dataclass
class Project(JsonSchemaMixin):

    id: str
    name: str
    scene_id: str
    action_points: List[ProjectActionPoint] = field(default_factory=list)
    desc: str = field(default_factory=str)
    has_logic: bool = True
    modified: Optional[datetime] = None
    int_modified: Optional[datetime] = None

    def bare(self) -> "Project":
        return Project(self.id, self.name, self.scene_id, desc=self.desc, has_logic=self.has_logic)

    def update_modified(self):
        self.int_modified = datetime.now(tz=timezone.utc)

    def has_changes(self) -> bool:

        if self.int_modified is None:
            return False

        if self.modified is None:
            return True

        return self.int_modified > self.modified

    @property
    def action_points_with_parent(self) -> List[ProjectActionPoint]:
        """
        Get action points which are relative to something (parent is set).
        :return:
        """

        return [ap for ap in self.action_points if ap.parent]

    @property
    def action_points_names(self) -> Set[str]:
        return {ap.name for ap in self.action_points}

    def ap_and_joints(self, joints_id: str) -> Tuple[ProjectActionPoint, ProjectRobotJoints]:

        for ap in self.action_points:
            for joints in ap.robot_joints:
                if joints.id == joints_id:
                    return ap, joints
        raise Arcor2Exception("Unknown joints.")

    def joints(self, joints_id: str) -> ProjectRobotJoints:
        return self.ap_and_joints(joints_id)[1]

    def ap_and_orientation(self, orientation_id: str) -> Tuple[ProjectActionPoint, NamedOrientation]:

        for ap in self.action_points:
            for ori in ap.orientations:
                if ori.id == orientation_id:
                    return ap, ori
        raise Arcor2Exception("Unknown orientation.")

    def orientation(self, orientation_id: str) -> NamedOrientation:
        return self.ap_and_orientation(orientation_id)[1]

    def action(self, action_id: str) -> Action:

        for ap in self.action_points:
            for ac in ap.actions:
                if ac.id == action_id:
                    return ac
        else:
            raise Arcor2Exception("Action not found")

    def action_point_and_action(self, action_id: str) -> Tuple[ProjectActionPoint, Action]:

        for ap in self.action_points:
            for ac in ap.actions:
                if ac.id == action_id:
                    return ap, ac
        else:
            raise Arcor2Exception("Action not found")

    def actions(self) -> List[Action]:
        return [act for ap in self.action_points for act in ap.actions]

    def action_ids(self) -> Set[str]:
        return {action.id for action in self.actions()}

    def action_user_names(self) -> Set[str]:
        return {action.name for action in self.actions()}

    def action_point(self, action_point_id: str) -> ProjectActionPoint:

        for ap in self.action_points:
            if ap.id == action_point_id:
                return ap
        else:
            raise Arcor2Exception("Action point not found")


@dataclass
class ProjectSources(JsonSchemaMixin):

    id: str  # project_id
    script: str


@dataclass
class IdDesc(JsonSchemaMixin):
    id: str
    name: str
    desc: Optional[str] = None


@dataclass
class IdDescList(JsonSchemaMixin):

    items: List[IdDesc] = field(default_factory=list)


class PackageStateEnum(Enum):

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
class PackageState(JsonSchemaMixin):

    state: PackageStateEnum = PackageStateEnum.STOPPED


@dataclass
class CurrentAction(JsonSchemaMixin):

    action_id: str = ""
    args: List[ActionParameter] = field(default_factory=list)


@dataclass
class BroadcastInfo(JsonSchemaMixin):

    host: str
    port: int
