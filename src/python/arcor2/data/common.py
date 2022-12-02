from __future__ import annotations

import abc
import copy
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, unique
from json import JSONEncoder
from typing import Any, Iterator, NamedTuple, Optional, TypeVar, cast

import fastuuid as uuid
import numpy as np
import quaternion
from dataclasses_jsonschema import DEFAULT_SCHEMA_TYPE, JsonSchemaMixin
from dataclasses_jsonschema.type_defs import JsonDict, SchemaType

from arcor2 import json
from arcor2.exceptions import Arcor2Exception


def uid(prefix: str) -> str:

    if not (prefix and prefix[0].isalpha() and prefix[-1] != "_"):
        raise Arcor2Exception(f"{prefix} is a invalid uid prefix.")

    return f"{prefix}_{uuid.uuid4().hex}"


@unique
class StrEnum(str, Enum):
    @classmethod
    def set(cls) -> set[str]:
        return set(map(lambda c: c.value, cls))  # type: ignore


@unique
class IntEnum(int, Enum):
    @classmethod
    def set(cls) -> set[int]:
        return set(map(lambda c: c.value, cls))  # type: ignore


class FlowTypes(StrEnum):

    DEFAULT: str = "default"


class LinkToActionOutput(NamedTuple):
    action_id: str
    flow_name: FlowTypes
    output_index: int


def parse_link(val: str) -> LinkToActionOutput:

    try:
        action_id, flow_name, output_idx_str = val.split("/")
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
        assert isinstance(attr, (float, int))
        return attr

    def __iter__(self) -> Iterator[float]:

        # filtering items starting with _ is necessary to allow runtime monkey-patching
        # ...otherwise those patched attributes will appear in e.g. list(Position(1,2,3))
        yield from [v for k, v in self.__dict__.items() if not k.startswith("_")]


@dataclass
class Position(IterableIndexable):

    x: float = 0.0
    y: float = 0.0
    z: float = 0.0

    def rotated(self, ori: Orientation, inverse: bool = False) -> Position:

        q = ori.as_quaternion()

        if inverse:
            q = q.inverse()

        rotated_vector = quaternion.rotate_vectors([q], [list(self)])[0][0]

        return Position(rotated_vector[0], rotated_vector[1], rotated_vector[2])

    def __eq__(self, other: object) -> bool:

        if not isinstance(other, Position):
            return False

        return np.allclose(list(self), list(other), rtol=1.0e-6)

    def __add__(self, other: object) -> Position:

        if not isinstance(other, Position):
            raise Arcor2Exception("Not a position.")

        return Position(self.x + other.x, self.y + other.y, self.z + other.z)

    def __iadd__(self, other: object) -> Position:

        if not isinstance(other, Position):
            raise ValueError

        self.x += other.x
        self.y += other.y
        self.z += other.z
        return self

    def __sub__(self, other) -> Position:

        if not isinstance(other, Position):
            raise Arcor2Exception("Not a position.")

        return Position(self.x - other.x, self.y - other.y, self.z - other.z)

    def __mul__(self, other: object) -> Position:

        if not isinstance(other, (float, int)):
            raise ValueError

        return Position(self.x * other, self.y * other, self.z * other)

    def __imul__(self, other: object) -> Position:

        if not isinstance(other, (float, int)):
            raise ValueError

        self.x *= other
        self.y *= other
        self.z *= other

        return self

    def to_dict(
        self,
        omit_none: bool = True,
        validate: bool = False,
        validate_enums: bool = True,
        schema_type: SchemaType = DEFAULT_SCHEMA_TYPE,
    ) -> JsonDict:

        # orjson does not like numpy.float64
        return {"x": float(self.x), "y": float(self.y), "z": float(self.z)}


@dataclass
class Orientation(IterableIndexable):

    x: float = 0.0
    y: float = 0.0
    z: float = 0.0
    w: float = 1.0

    @classmethod
    def from_rotation_vector(cls, x: float = 0.0, y: float = 0.0, z: float = 0.0) -> Orientation:
        return cls.from_quaternion(quaternion.from_rotation_vector([x, y, z]))

    @classmethod
    def from_quaternion(cls, q: quaternion.quaternion) -> Orientation:
        return Orientation(q.x, q.y, q.z, q.w)

    @staticmethod
    def _normalized(q: quaternion.quaternion) -> quaternion.quaternion:

        nq = q.normalized()

        if nq.isnan():
            raise Arcor2Exception("Invalid quaternion.")

        return nq

    def inverse(self) -> None:
        self.set_from_quaternion(self.as_quaternion().inverse())

    def inversed(self) -> Orientation:
        return self.from_quaternion(self.as_quaternion().inverse())

    def as_quaternion(self) -> quaternion.quaternion:
        return self._normalized(quaternion.quaternion(self.w, self.x, self.y, self.z))

    def set_from_quaternion(self, q: quaternion.quaternion) -> None:

        nq = self._normalized(q)

        self.x = nq.x
        self.y = nq.y
        self.z = nq.z
        self.w = nq.w

    def as_tr_matrix(self) -> np.ndarray:
        """Returns 4x4 transformation matrix.

        :return:
        """

        arr = np.empty((4, 4))
        arr[:3, :3] = quaternion.as_rotation_matrix(self.as_quaternion())
        arr[3, :] = [0, 0, 0, 1]
        return arr

    def __eq__(self, other: object) -> bool:

        if not isinstance(other, Orientation):
            return False

        return cast(bool, quaternion.isclose(self.as_quaternion(), other.as_quaternion(), rtol=1.0e-6)[0])

    def __mul__(self, other: object) -> Orientation:

        if not isinstance(other, Orientation):
            raise ValueError

        return self.from_quaternion(self.as_quaternion() * other.as_quaternion())

    def __imul__(self, other: object) -> Orientation:

        if not isinstance(other, Orientation):
            raise ValueError

        self.set_from_quaternion(other.as_quaternion() * self.as_quaternion())
        return self

    def __post_init__(self):

        nq = self.as_quaternion()  # in order to get normalized quaternion

        self.x = nq.x
        self.y = nq.y
        self.z = nq.z
        self.w = nq.w

    def to_dict(
        self,
        omit_none: bool = True,
        validate: bool = False,
        validate_enums: bool = True,
        schema_type: SchemaType = DEFAULT_SCHEMA_TYPE,
    ) -> JsonDict:

        # orjson does not like numpy.float64
        return {"x": float(self.x), "y": float(self.y), "z": float(self.z), "w": float(self.w)}


class ModelMixin(abc.ABC):
    """Mixin for objects with 'id' property that is uuid."""

    id: str

    @classmethod
    @abc.abstractmethod
    def uid_prefix(cls) -> str:
        pass

    @classmethod
    def uid(cls) -> str:
        """Returns uid with proper prefix.

        :return:
        """
        return uid(cls.uid_prefix())

    def __post_init__(self) -> None:
        if not self.id:
            self.id = self.uid()


@dataclass
class NamedOrientation(JsonSchemaMixin, ModelMixin):

    name: str
    orientation: Orientation
    id: str = ""

    @classmethod
    def uid_prefix(cls) -> str:
        return "ori"

    def copy(self) -> NamedOrientation:
        c = copy.deepcopy(self)
        c.id = self.uid()
        return c


@dataclass
class Pose(JsonSchemaMixin):

    position: Position = field(default_factory=Position)
    orientation: Orientation = field(default_factory=Orientation)

    def as_tr_matrix(self) -> np.ndarray:

        arr = np.empty((4, 4))
        arr[:3, :3] = quaternion.as_rotation_matrix(self.orientation.as_quaternion())
        arr[:3, 3] = list(self.position)
        arr[3, :] = [0, 0, 0, 1]
        return arr

    @staticmethod
    def from_tr_matrix(matrix: np.ndarray) -> Pose:

        tvec = matrix[:3, 3]
        return Pose(
            Position(tvec[0], tvec[1], tvec[2]),
            Orientation.from_quaternion(quaternion.from_rotation_matrix(matrix[:3, :3])),
        )

    def inversed(self) -> Pose:

        inv = self.orientation.inversed()
        return Pose((self.position * -1).rotated(inv), inv)


@dataclass
class ActionMetadata(JsonSchemaMixin):

    composite: bool = field(metadata=dict(description="Should be set for nested actions."), default=False)
    hidden: bool = field(metadata=dict(description="When set, action will be hidden in UIs."), default=False)
    cancellable: bool = field(
        init=False, default=False, metadata=dict(description="Defines whether action execution can be cancelled.")
    )


@dataclass
class Joint(JsonSchemaMixin):

    name: str
    value: float


@dataclass
class ProjectRobotJoints(JsonSchemaMixin, ModelMixin):

    name: str
    robot_id: str
    joints: list[Joint]
    is_valid: bool = False
    arm_id: Optional[str] = None
    end_effector_id: Optional[str] = None
    id: str = ""

    @classmethod
    def uid_prefix(cls) -> str:
        return "joi"

    def copy(self) -> ProjectRobotJoints:
        c = copy.deepcopy(self)
        c.id = self.uid()
        return c


@dataclass
class Parameter(JsonSchemaMixin):

    name: str
    type: str
    value: str


@dataclass
class SceneObject(JsonSchemaMixin, ModelMixin):

    name: str
    type: str
    pose: Optional[Pose] = None
    parameters: list[Parameter] = field(default_factory=list)
    id: str = ""

    @classmethod
    def uid_prefix(cls) -> str:
        return "obj"

    def copy(self) -> SceneObject:
        c = copy.deepcopy(self)
        c.id = self.uid()
        return c


@dataclass
class BareScene(JsonSchemaMixin, ModelMixin):

    name: str
    description: str = field(default_factory=str)
    created: Optional[datetime] = None
    modified: Optional[datetime] = None
    int_modified: Optional[datetime] = None
    id: str = ""

    @classmethod
    def uid_prefix(cls) -> str:
        return "scn"

    SCN = TypeVar("SCN", bound="BareScene")

    def copy(self: SCN) -> SCN:
        c = copy.deepcopy(self)
        c.id = self.uid()
        return c


@dataclass
class Scene(BareScene):

    objects: list[SceneObject] = field(default_factory=list)

    @staticmethod
    def from_bare(bare: BareScene) -> Scene:
        return Scene(bare.name, bare.description, bare.created, bare.modified, bare.int_modified, id=bare.id)


@dataclass
class IdValue(JsonSchemaMixin):

    id: str
    value: str


class ActionParameterException(Arcor2Exception):
    pass


@dataclass
class ActionParameter(Parameter):
    class TypeEnum(StrEnum):

        PROJECT_PARAMETER: str = "project_parameter"
        LINK: str = "link"

    def str_from_value(self) -> str:

        val = json.loads(self.value)

        if not isinstance(val, str):
            raise Arcor2Exception("Value should be string.")

        return val

    def parse_link(self) -> LinkToActionOutput:
        if self.type != self.TypeEnum.LINK:
            raise Arcor2Exception("Not a link.")

        return parse_link(self.str_from_value())

    def is_value(self) -> bool:
        return self.type not in self.TypeEnum.set()


@dataclass
class Flow(JsonSchemaMixin):

    type: FlowTypes = FlowTypes.DEFAULT
    outputs: list[str] = field(default_factory=list)  # can't be set as it is unordered

    def __post_init__(self) -> None:

        if len(self.outputs) > len(set(self.outputs)):
            raise Arcor2Exception("Outputs have to be unique.")


@dataclass
class BareAction(JsonSchemaMixin, ModelMixin):

    name: str
    type: str
    id: str = ""

    @classmethod
    def uid_prefix(cls) -> str:
        return "act"

    ACT = TypeVar("ACT", bound="BareAction")

    def copy(self: ACT) -> ACT:
        c = copy.deepcopy(self)
        c.id = self.uid()
        return c


@dataclass
class Action(BareAction):
    class ParsedType(NamedTuple):

        obj_id: str
        action_type: str

    parameters: list[ActionParameter] = field(default_factory=list)
    flows: list[Flow] = field(default_factory=list)

    def parse_type(self) -> ParsedType:

        try:
            obj_id_str, action = self.type.split("/")
        except ValueError:
            raise Arcor2Exception(f"Action: {self.id} has invalid type: {self.type}.")
        return self.ParsedType(obj_id_str, action)

    def parameter(self, parameter_id: str) -> ActionParameter:

        for param in self.parameters:
            if parameter_id == param.name:
                return param

        raise Arcor2Exception("Param not found")

    @property
    def bare(self) -> BareAction:
        return BareAction(self.name, self.type, id=self.id)

    def flow(self, flow_type: FlowTypes = FlowTypes.DEFAULT) -> Flow:

        for flow in self.flows:
            if flow.type == flow_type:
                return flow
        raise Arcor2Exception(f"Flow '{flow_type.value}' not found.")


@dataclass
class BareActionPoint(JsonSchemaMixin, ModelMixin):

    name: str
    position: Position
    parent: Optional[str] = None
    display_name: Optional[str] = None
    description: Optional[str] = None
    id: str = ""

    @classmethod
    def uid_prefix(cls) -> str:
        return "acp"

    ACP = TypeVar("ACP", bound="BareActionPoint")

    def copy(self: ACP) -> ACP:
        c = copy.deepcopy(self)
        c.id = self.uid()
        return c


@dataclass
class ActionPoint(BareActionPoint):

    orientations: list[NamedOrientation] = field(default_factory=list)
    robot_joints: list[ProjectRobotJoints] = field(default_factory=list)
    actions: list[Action] = field(default_factory=list)

    @staticmethod
    def from_bare(bare: BareActionPoint) -> ActionPoint:
        return ActionPoint(bare.name, bare.position, bare.parent, bare.display_name, bare.description, id=bare.id)


@dataclass
class ProjectLogicIf(JsonSchemaMixin):

    what: str
    value: str

    def parse_what(self) -> LinkToActionOutput:
        return parse_link(self.what)


@dataclass
class LogicItem(JsonSchemaMixin, ModelMixin):
    class ParsedStart(NamedTuple):

        start_action_id: str
        start_flow: str

    # TODO can't be ClassVar because of https://github.com/s-knibbs/dataclasses-jsonschema/issues/176
    START = "START"
    END = "END"

    start: str
    end: str
    condition: Optional[ProjectLogicIf] = None
    id: str = ""

    def parse_start(self) -> ParsedStart:

        try:
            start_action_id, start_flow = self.start.split("/")
        except ValueError:
            return self.ParsedStart(self.start, FlowTypes.DEFAULT)

        return self.ParsedStart(start_action_id, start_flow)

    @classmethod
    def uid_prefix(cls) -> str:
        return "lit"

    def copy(self) -> LogicItem:
        c = copy.deepcopy(self)
        c.id = self.uid()
        return c


@dataclass
class Range(JsonSchemaMixin):
    # TODO when nested in ProjectParameter, ProjectParameter.from_dict({}) raises NameError: name 'Range' is not defined

    min: float
    max: float


@dataclass
class ProjectParameter(Parameter, ModelMixin):

    range: Optional[Range] = None  # TODO use it in parameter plugins?
    display_name: Optional[str] = None
    description: Optional[str] = None
    id: str = ""

    @classmethod
    def uid_prefix(cls) -> str:
        return "pco"


@dataclass
class FunctionReturns(JsonSchemaMixin):

    type: str
    link: str


@dataclass
class ProjectFunction(JsonSchemaMixin, ModelMixin):

    name: str
    actions: list[Action] = field(default_factory=list)
    logic: list[LogicItem] = field(default_factory=list)
    parameters: list[ActionParameter] = field(default_factory=list)
    returns: list[FunctionReturns] = field(default_factory=list)
    id: str = ""

    def action_ids(self) -> set[str]:
        return {act.id for act in self.actions}

    def action(self, action_id: str) -> Action:

        for ac in self.actions:
            if ac.id == action_id:
                return ac
        else:
            raise Arcor2Exception("Action not found")

    @classmethod
    def uid_prefix(cls) -> str:
        return "pfu"

    def copy(self) -> ProjectFunction:
        c = copy.deepcopy(self)
        c.id = self.uid()
        return c


@dataclass
class SceneObjectOverride(JsonSchemaMixin):

    id: str  # object id
    parameters: list[Parameter]


@dataclass
class BareProject(JsonSchemaMixin, ModelMixin):

    name: str
    scene_id: str
    description: str = field(default_factory=str)
    has_logic: bool = True
    created: Optional[datetime] = None
    modified: Optional[datetime] = None
    int_modified: Optional[datetime] = None
    id: str = ""

    @classmethod
    def uid_prefix(cls) -> str:
        return "pro"

    PRO = TypeVar("PRO", bound="BareProject")

    def copy(self: PRO) -> PRO:
        c = copy.deepcopy(self)
        c.id = self.uid()
        return c


@dataclass
class Project(BareProject):

    action_points: list[ActionPoint] = field(default_factory=list)
    parameters: list[ProjectParameter] = field(default_factory=list)
    functions: list[ProjectFunction] = field(default_factory=list)
    logic: list[LogicItem] = field(default_factory=list)
    object_overrides: list[SceneObjectOverride] = field(default_factory=list)
    project_objects_ids: Optional[list[str]] = None  # not used at the moment

    @staticmethod
    def from_bare(bare: BareProject) -> Project:
        return Project(
            bare.name,
            bare.scene_id,
            bare.description,
            bare.has_logic,
            bare.created,
            bare.modified,
            bare.int_modified,
            id=bare.id,
        )


@dataclass
class ProjectSources(JsonSchemaMixin):

    id: str  # project_id
    script: str


@dataclass
class IdDesc(JsonSchemaMixin):
    id: str
    name: str
    created: datetime
    modified: datetime
    description: Optional[str] = None


@dataclass
class BroadcastInfo(JsonSchemaMixin):

    host: str
    port: int


@dataclass
class Error(JsonSchemaMixin):
    code: int
    detail: str
    type: Optional[str] = None
    data: Optional[str] = None


@dataclass
class WebApiError(JsonSchemaMixin, Arcor2Exception):
    service: str
    message: str
    type: str
    description: str
    content: Optional[str] = None

    def __str__(self):
        return f"{self.service} ({self.type}): {self.message}"
