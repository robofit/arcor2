# -*- coding: utf-8 -*-

from typing import List, Set

from dataclasses import dataclass, field
from dataclasses_jsonschema import JsonSchemaMixin

from arcor2.data.common import IdValue, StrEnum
from arcor2.data.object_type import ObjectTypeMeta, ObjectActions
from arcor2.data.rpc.common import IdArgs, Request, Response, wo_suffix, TypeArgs, RobotArg


@dataclass
class ActionParamValuesArgs(JsonSchemaMixin):

    id: str = field(metadata=dict(description="Object or service id."))
    param_id: str
    parent_params: List[IdValue] = field(default_factory=list)


@dataclass
class ActionParamValuesRequest(Request):

    args: ActionParamValuesArgs
    request: str = field(default=wo_suffix(__qualname__), init=False)  # type: ignore  # noqa: F821


@dataclass
class ActionParamValuesResponse(Response):

    data: Set[str] = field(default_factory=set)  # TODO what about other (possible) types?
    response: str = field(default=ActionParamValuesRequest.request, init=False)


# ----------------------------------------------------------------------------------------------------------------------


@dataclass
class GetObjectTypesRequest(Request):

    request: str = field(default=wo_suffix(__qualname__), init=False)  # type: ignore  # noqa: F821


@dataclass
class GetObjectTypesResponse(Response):

    data: List[ObjectTypeMeta] = field(default_factory=list)
    response: str = field(default=GetObjectTypesRequest.request, init=False)


# ----------------------------------------------------------------------------------------------------------------------


@dataclass
class GetActionsRequest(Request):

    args: TypeArgs
    request: str = field(default=wo_suffix(__qualname__), init=False)  # type: ignore  # noqa: F821


@dataclass
class GetActionsResponse(Response):

    data: ObjectActions = field(default_factory=list)
    response: str = field(default=GetActionsRequest.request, init=False)


# ----------------------------------------------------------------------------------------------------------------------


@dataclass
class NewObjectTypeRequest(Request):

    args: ObjectTypeMeta
    dry_run: bool = False
    request: str = field(default=wo_suffix(__qualname__), init=False)  # type: ignore  # noqa: F821


@dataclass
class NewObjectTypeResponse(Response):

    response: str = field(default=NewObjectTypeRequest.request, init=False)


# ----------------------------------------------------------------------------------------------------------------------


@dataclass
class FocusObjectStartRequestArgs(JsonSchemaMixin):

    object_id: str
    robot: RobotArg


@dataclass
class FocusObjectStartRequest(Request):

    args: FocusObjectStartRequestArgs
    request: str = field(default=wo_suffix(__qualname__), init=False)  # type: ignore  # noqa: F821


@dataclass
class FocusObjectStartResponse(Response):

    response: str = field(default=FocusObjectStartRequest.request, init=False)


# ----------------------------------------------------------------------------------------------------------------------


@dataclass
class FocusObjectRequestArgs(JsonSchemaMixin):

    object_id: str
    point_idx: int


@dataclass
class FocusObjectRequest(Request):

    args: FocusObjectRequestArgs
    request: str = field(default=wo_suffix(__qualname__), init=False)  # type: ignore  # noqa: F821


@dataclass
class FocusObjectResponseData(JsonSchemaMixin):

    finished_indexes: List[int] = field(default_factory=list)


@dataclass
class FocusObjectResponse(Response):

    data: FocusObjectResponseData = field(default_factory=FocusObjectResponseData)
    response: str = field(default=FocusObjectRequest.request, init=False)


# ----------------------------------------------------------------------------------------------------------------------


@dataclass
class FocusObjectDoneRequest(Request):

    args: IdArgs
    request: str = field(default=wo_suffix(__qualname__), init=False)  # type: ignore  # noqa: F821


@dataclass
class FocusObjectDoneResponse(Response):

    data: FocusObjectResponseData = field(default_factory=FocusObjectResponseData)
    response: str = field(default=FocusObjectDoneRequest.request, init=False)


# ----------------------------------------------------------------------------------------------------------------------

class PivotEnum(StrEnum):
    TOP: str = "top"
    MIDDLE: str = "middle"
    BOTTOM: str = "bottom"


@dataclass
class UpdateObjectPoseUsingRobotArgs(IdArgs):

    robot: RobotArg
    pivot: PivotEnum = PivotEnum.MIDDLE


@dataclass
class UpdateObjectPoseUsingRobotRequest(Request):

    args: UpdateObjectPoseUsingRobotArgs
    request: str = field(default=wo_suffix(__qualname__), init=False)  # type: ignore  # noqa: F821


@dataclass
class UpdateObjectPoseUsingRobotResponse(Response):

    response: str = field(default=UpdateObjectPoseUsingRobotRequest.request, init=False)
