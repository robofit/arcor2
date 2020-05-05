# -*- coding: utf-8 -*-

from typing import List, Set
from dataclasses import dataclass, field

from dataclasses_jsonschema import JsonSchemaMixin

from arcor2.data.robot import RobotMeta
from arcor2.data.common import Joint, Pose, StrEnum
from arcor2.data.rpc.common import Request, Response, wo_suffix


@dataclass
class GetRobotMetaRequest(Request):

    request: str = field(default=wo_suffix(__qualname__), init=False)  # type: ignore  # noqa: F821


@dataclass
class GetRobotMetaResponse(Response):

    data: List[RobotMeta] = field(default_factory=list)
    response: str = field(default=GetRobotMetaRequest.request, init=False)

# ----------------------------------------------------------------------------------------------------------------------


@dataclass
class GetRobotJointsArgs(JsonSchemaMixin):

    robot_id: str


@dataclass
class GetRobotJointsRequest(Request):

    args: GetRobotJointsArgs
    request: str = field(default=wo_suffix(__qualname__), init=False)  # type: ignore  # noqa: F821


@dataclass
class GetRobotJointsResponse(Response):

    data: List[Joint] = field(default_factory=list)
    response: str = field(default=GetRobotJointsRequest.request, init=False)

# ----------------------------------------------------------------------------------------------------------------------


@dataclass
class GetEndEffectorPoseArgs(JsonSchemaMixin):

    robot_id: str
    end_effector_id: str


@dataclass
class GetEndEffectorPoseRequest(Request):

    args: GetEndEffectorPoseArgs
    request: str = field(default=wo_suffix(__qualname__), init=False)  # type: ignore  # noqa: F821


@dataclass
class GetEndEffectorPoseResponse(Response):

    data: Pose = field(default_factory=Pose)
    response: str = field(default=GetEndEffectorPoseRequest.request, init=False)

# ----------------------------------------------------------------------------------------------------------------------


@dataclass
class GetEndEffectorsArgs(JsonSchemaMixin):

    robot_id: str


@dataclass
class GetEndEffectorsRequest(Request):

    args: GetEndEffectorsArgs
    request: str = field(default=wo_suffix(__qualname__), init=False)  # type: ignore  # noqa: F821


@dataclass
class GetEndEffectorsResponse(Response):

    data: Set[str] = field(default_factory=set)
    response: str = field(default=GetEndEffectorsRequest.request, init=False)

# ----------------------------------------------------------------------------------------------------------------------


@dataclass
class GetGrippersArgs(JsonSchemaMixin):

    robot_id: str


@dataclass
class GetGrippersRequest(Request):

    args: GetGrippersArgs
    request: str = field(default=wo_suffix(__qualname__), init=False)  # type: ignore  # noqa: F821


@dataclass
class GetGrippersResponse(Response):

    data: Set[str] = field(default_factory=set)
    response: str = field(default=GetGrippersRequest.request, init=False)

# ----------------------------------------------------------------------------------------------------------------------


@dataclass
class GetSuctionsArgs(JsonSchemaMixin):

    robot_id: str


@dataclass
class GetSuctionsRequest(Request):

    args: GetSuctionsArgs
    request: str = field(default=wo_suffix(__qualname__), init=False)  # type: ignore  # noqa: F821


@dataclass
class GetSuctionsResponse(Response):

    data: Set[str] = field(default_factory=set)
    response: str = field(default=GetSuctionsRequest.request, init=False)

# ----------------------------------------------------------------------------------------------------------------------


class RegisterEnum(StrEnum):

    EEF_POSE: str = "eef_pose"
    JOINTS: str = "joints"


@dataclass
class RegisterForRobotEventArgs(JsonSchemaMixin):

    robot_id: str
    what: RegisterEnum
    send: bool


@dataclass
class RegisterForRobotEventRequest(Request):

    args: RegisterForRobotEventArgs
    request: str = field(default=wo_suffix(__qualname__), init=False)  # type: ignore  # noqa: F821


@dataclass
class RegisterForRobotEventResponse(Response):

    data: Set[str] = field(default_factory=set)
    response: str = field(default=RegisterForRobotEventRequest.request, init=False)
