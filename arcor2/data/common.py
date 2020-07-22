#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, unique
from json import JSONEncoder
from typing import Any, ClassVar, Iterator, List, NamedTuple, Optional, Set, cast

from dataclasses_jsonschema import JsonSchemaMixin

import quaternion  # type: ignore

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


class FlowTypes(StrEnum):

    DEFAULT: str = "default"


class LinkToActionOutput(NamedTuple):
    action_id: str
    flow_name: FlowTypes
    output_index: int


def parse_link(val: str) -> LinkToActionOutput:

    action_id, flow_name, output_idx_str = val.split("/")

    try:
        return LinkToActionOutput(action_id, FlowTypes(flow_name), int(output_idx_str))
    except ValueError as e:
        raise Arcor2Exception("Invalid link value.") from e


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

    def __eq__(self, other: object) -> bool:

        if not isinstance(other, Orientation):
            return False

        return cast(bool, quaternion.isclose(self.as_quaternion(), other.as_quaternion(), rtol=1.e-8)[0])


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

    def orientation_names(self) -> Set[str]:
        return {ori.name for ori in self.orientations}

    def joints_names(self) -> Set[str]:
        return {joints.name for joints in self.robot_joints}

    def invalidate_joints(self) -> None:

        for joints in self.robot_joints:
            joints.is_valid = False


@dataclass
class SceneObjectSetting(JsonSchemaMixin):

    key: str
    type: str
    value: str


@dataclass
class SceneObject(JsonSchemaMixin):

    id: str
    name: str
    type: str
    pose: Optional[Pose] = None
    settings: List[SceneObjectSetting] = field(default_factory=list)
    children: List["SceneObject"] = field(default_factory=list)


@dataclass
class Scene(JsonSchemaMixin):

    id: str
    name: str
    objects: List[SceneObject] = field(default_factory=list)
    desc: str = field(default_factory=str)
    modified: Optional[datetime] = None
    int_modified: Optional[datetime] = None


@dataclass
class IdValue(JsonSchemaMixin):

    id: str
    value: str


class ActionParameterException(Arcor2Exception):
    pass


@dataclass
class ActionParameter(JsonSchemaMixin):

    class TypeEnum(StrEnum):

        CONSTANT: str = "constant"
        LINK: str = "link"

    id: str
    type: str
    value: str

    def parse_link(self) -> LinkToActionOutput:
        assert self.type == ActionParameter.TypeEnum.LINK
        return parse_link(self.value)

    def is_value(self) -> bool:
        return self.type not in ActionParameter.TypeEnum.set()


@dataclass
class Flow(JsonSchemaMixin):

    type: FlowTypes = FlowTypes.DEFAULT
    outputs: List[str] = field(default_factory=list)  # can't be set as it is unordered

    def __post_init__(self) -> None:

        if len(self.outputs) > len(set(self.outputs)):
            raise Arcor2Exception("Outputs have to be unique.")


@dataclass
class Action(JsonSchemaMixin):

    class ParsedType(NamedTuple):

        obj_id: str
        action_type: str

    id: str
    name: str
    type: str
    parameters: List[ActionParameter] = field(default_factory=list)
    flows: List[Flow] = field(default_factory=list)

    def parse_type(self) -> ParsedType:

        try:
            obj_id_str, action = self.type.split("/")
        except ValueError:
            raise Arcor2Exception(f"Action: {self.id} has invalid type: {self.type}.")
        return Action.ParsedType(obj_id_str, action)

    def parameter(self, parameter_id: str) -> ActionParameter:

        for param in self.parameters:
            if parameter_id == param.id:
                return param

        raise Arcor2Exception("Param not found")

    @property
    def bare(self) -> "Action":
        return Action(self.id, self.name, self.type)

    def flow(self, flow_type: FlowTypes = FlowTypes.DEFAULT) -> Flow:

        for flow in self.flows:
            if flow.type == flow_type:
                return flow
        raise Arcor2Exception(f"Flow '{flow_type.value}' not found.")


@dataclass
class ProjectActionPoint(ActionPoint):

    actions: List[Action] = field(default_factory=list)

    def action_ids(self) -> Set[str]:
        return {action.id for action in self.actions}

    def bare(self) -> "ProjectActionPoint":
        return ProjectActionPoint(self.id, self.name, self.position, self.parent)


@dataclass
class ProjectLogicIf(JsonSchemaMixin):

    what: str
    value: str

    def parse_what(self) -> LinkToActionOutput:
        return parse_link(self.what)


@dataclass
class LogicItem(JsonSchemaMixin):

    class ParsedStart(NamedTuple):

        start_action_id: str
        start_flow: str

    START: ClassVar[str] = "START"
    END: ClassVar[str] = "END"

    id: str
    start: str
    end: str
    condition: Optional[ProjectLogicIf] = None

    def parse_start(self) -> ParsedStart:

        try:
            start_action_id, start_flow = self.start.split("/")
        except ValueError:
            return LogicItem.ParsedStart(self.start, FlowTypes.DEFAULT)

        return LogicItem.ParsedStart(start_action_id, start_flow)


@dataclass
class ProjectConstant(JsonSchemaMixin):

    id: str
    name: str
    type: str
    value: str


@dataclass
class FunctionReturns(JsonSchemaMixin):

    type: str
    link: str


@dataclass
class ProjectFunction(JsonSchemaMixin):

    id: str
    name: str
    actions: List[Action] = field(default_factory=list)
    logic: List[LogicItem] = field(default_factory=list)
    parameters: List[ActionParameter] = field(default_factory=list)
    returns: List[FunctionReturns] = field(default_factory=list)

    def action_ids(self) -> Set[str]:
        return {act.id for act in self.actions}

    def action(self, action_id: str) -> Action:

        for ac in self.actions:
            if ac.id == action_id:
                return ac
        else:
            raise Arcor2Exception("Action not found")


@dataclass
class Project(JsonSchemaMixin):

    id: str
    name: str
    scene_id: str
    desc: str = field(default_factory=str)
    has_logic: bool = True
    modified: Optional[datetime] = None
    int_modified: Optional[datetime] = None
    action_points: List[ProjectActionPoint] = field(default_factory=list)
    constants: List[ProjectConstant] = field(default_factory=list)
    functions: List[ProjectFunction] = field(default_factory=list)
    logic: List[LogicItem] = field(default_factory=list)


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
    UNDEFINED: str = "undefined"


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

    state: PackageStateEnum = PackageStateEnum.UNDEFINED
    package_id: Optional[str] = None


@dataclass
class CurrentAction(JsonSchemaMixin):

    action_id: str = ""
    args: List[ActionParameter] = field(default_factory=list)


@dataclass
class BroadcastInfo(JsonSchemaMixin):

    host: str
    port: int
