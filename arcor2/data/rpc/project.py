# -*- coding: utf-8 -*-

from typing import List, Optional

from dataclasses import dataclass, field
from dataclasses_jsonschema import JsonSchemaMixin

from arcor2.data.common import IdDesc, Position, ActionParameter, ActionIO, Orientation
from arcor2.data.rpc.common import IdArgs, Request, Response, wo_suffix, RobotArg


@dataclass
class NewProjectRequestArgs(JsonSchemaMixin):

    scene_id: str
    user_id: str
    desc: str = field(default_factory=str)
    has_logic: bool = True


@dataclass
class NewProjectRequest(Request):

    args: NewProjectRequestArgs
    request: str = field(default=wo_suffix(__qualname__), init=False)  # type: ignore  # noqa: F821


@dataclass
class NewProjectResponse(Response):

    response: str = field(default=NewProjectRequest.request, init=False)

# ----------------------------------------------------------------------------------------------------------------------


@dataclass
class CloseProjectRequestArgs(JsonSchemaMixin):

    id: str
    force: bool = False


@dataclass
class CloseProjectRequest(Request):

    args: CloseProjectRequestArgs
    request: str = field(default=wo_suffix(__qualname__), init=False)  # type: ignore  # noqa: F821


@dataclass
class CloseProjectResponse(Response):

    response: str = field(default=CloseProjectRequest.request, init=False)

# ----------------------------------------------------------------------------------------------------------------------


@dataclass
class SaveProjectRequest(Request):

    request: str = field(default=wo_suffix(__qualname__), init=False)  # type: ignore  # noqa: F821


@dataclass
class SaveProjectResponse(Response):

    response: str = field(default=SaveProjectRequest.request, init=False)


# ----------------------------------------------------------------------------------------------------------------------


@dataclass
class OpenProjectRequest(Request):

    args: IdArgs
    request: str = field(default=wo_suffix(__qualname__), init=False)  # type: ignore  # noqa: F821


@dataclass
class OpenProjectResponse(Response):

    response: str = field(default=OpenProjectRequest.request, init=False)


# ----------------------------------------------------------------------------------------------------------------------


@dataclass
class ListProjectsResponseData(IdDesc):

    scene_id: str = field(default_factory=str)
    valid: bool = field(default=False, metadata=dict(description="Objects and their actions exists."))
    executable: bool = field(default=False, metadata=dict(description="Logic is defined and valid."))
    problems: List[str] = field(default_factory=list)


@dataclass
class ListProjectsRequest(Request):

    request: str = field(default=wo_suffix(__qualname__), init=False)  # type: ignore  # noqa: F821


@dataclass
class ListProjectsResponse(Response):

    data: List[ListProjectsResponseData] = field(default_factory=list)
    response: str = field(default=ListProjectsRequest.request, init=False)


# ----------------------------------------------------------------------------------------------------------------------

@dataclass
class ExecuteActionArgs(JsonSchemaMixin):

    action_id: str = field(metadata=dict(description="ID of the action to be executed."))


@dataclass
class ExecuteActionRequest(Request):

    args: ExecuteActionArgs
    request: str = field(default=wo_suffix(__qualname__), init=False)  # type: ignore  # noqa: F821


@dataclass
class ExecuteActionResponse(Response):

    response: str = field(default=ExecuteActionRequest.request, init=False)

# ----------------------------------------------------------------------------------------------------------------------


@dataclass
class AddActionPointArgs(JsonSchemaMixin):

    user_id: str
    position: Position
    parent: Optional[str] = None


@dataclass
class AddActionPointRequest(Request):

    args: AddActionPointArgs
    request: str = field(default=wo_suffix(__qualname__), init=False)  # type: ignore  # noqa: F821


@dataclass
class AddActionPointResponse(Response):

    response: str = field(default=AddActionPointRequest.request, init=False)

# ----------------------------------------------------------------------------------------------------------------------


@dataclass
class AddActionPointJointsRequestArgs(JsonSchemaMixin):

    action_point_id: str
    robot_id: str
    user_id: str = "default"


@dataclass
class AddActionPointJointsRequest(Request):

    args: AddActionPointJointsRequestArgs
    request: str = field(default=wo_suffix(__qualname__), init=False)  # type: ignore  # noqa: F821


@dataclass
class AddActionPointJointsResponse(Response):

    response: str = field(default=AddActionPointJointsRequest.request, init=False)

# ----------------------------------------------------------------------------------------------------------------------


@dataclass
class UpdateActionPointRequestArgs(JsonSchemaMixin):

    action_point_id: str
    new_parent_id: Optional[str] = None
    new_user_id: Optional[str] = None
    new_position: Optional[Position] = None


@dataclass
class UpdateActionPointRequest(Request):

    args: UpdateActionPointRequestArgs
    request: str = field(default=wo_suffix(__qualname__), init=False)  # type: ignore  # noqa: F821


@dataclass
class UpdateActionPointResponse(Response):

    response: str = field(default=UpdateActionPointRequest.request, init=False)


# ----------------------------------------------------------------------------------------------------------------------


@dataclass
class UpdateActionPointUsingRobotRequestArgs(JsonSchemaMixin):

    action_point_id: str
    robot: RobotArg


@dataclass
class UpdateActionPointUsingRobotRequest(Request):

    args: UpdateActionPointUsingRobotRequestArgs
    request: str = field(default=wo_suffix(__qualname__), init=False)  # type: ignore  # noqa: F821


@dataclass
class UpdateActionPointUsingRobotResponse(Response):

    response: str = field(default=UpdateActionPointUsingRobotRequest.request, init=False)

# ----------------------------------------------------------------------------------------------------------------------


@dataclass
class AddActionPointOrientationUsingRobotRequestArgs(JsonSchemaMixin):

    action_point_id: str
    robot: RobotArg
    user_id: str = "default"


@dataclass
class AddActionPointOrientationUsingRobotRequest(Request):

    args: AddActionPointOrientationUsingRobotRequestArgs
    request: str = field(default=wo_suffix(__qualname__), init=False)  # type: ignore  # noqa: F821


@dataclass
class AddActionPointOrientationUsingRobotResponse(Response):

    response: str = field(default=AddActionPointOrientationUsingRobotRequest.request, init=False)

# ----------------------------------------------------------------------------------------------------------------------


@dataclass
class UpdateActionPointOrientationUsingRobotRequestArgs(JsonSchemaMixin):

    action_point_id: str
    robot: RobotArg
    orientation_id: str


@dataclass
class UpdateActionPointOrientationUsingRobotRequest(Request):

    args: UpdateActionPointOrientationUsingRobotRequestArgs
    request: str = field(default=wo_suffix(__qualname__), init=False)  # type: ignore  # noqa: F821


@dataclass
class UpdateActionPointOrientationUsingRobotResponse(Response):

    response: str = field(default=UpdateActionPointOrientationUsingRobotRequest.request, init=False)

# ----------------------------------------------------------------------------------------------------------------------


@dataclass
class AddActionPointOrientationRequestArgs(JsonSchemaMixin):

    action_point_id: str
    orientation: Orientation
    user_id: str = "default"


@dataclass
class AddActionPointOrientationRequest(Request):

    args: AddActionPointOrientationRequestArgs
    request: str = field(default=wo_suffix(__qualname__), init=False)  # type: ignore  # noqa: F821


@dataclass
class AddActionPointOrientationResponse(Response):

    response: str = field(default=AddActionPointOrientationRequest.request, init=False)

# ----------------------------------------------------------------------------------------------------------------------


@dataclass
class UpdateActionPointOrientationRequestArgs(JsonSchemaMixin):

    action_point_id: str
    orientation_id: str
    orientation: Orientation


@dataclass
class UpdateActionPointOrientationRequest(Request):

    args: UpdateActionPointOrientationRequestArgs
    request: str = field(default=wo_suffix(__qualname__), init=False)  # type: ignore  # noqa: F821


@dataclass
class UpdateActionPointOrientationResponse(Response):

    response: str = field(default=UpdateActionPointOrientationRequest.request, init=False)


# ----------------------------------------------------------------------------------------------------------------------


@dataclass
class RemoveActionPointOrientationRequestArgs(JsonSchemaMixin):
    action_point_id: str
    orientation_id: str


@dataclass
class RemoveActionPointOrientationRequest(Request):
    args: RemoveActionPointOrientationRequestArgs
    request: str = field(default=wo_suffix(__qualname__), init=False)  # type: ignore  # noqa: F821


@dataclass
class RemoveActionPointOrientationResponse(Response):
    response: str = field(default=RemoveActionPointOrientationRequest.request, init=False)

# ----------------------------------------------------------------------------------------------------------------------


@dataclass
class AddActionRequestArgs(JsonSchemaMixin):

    action_point_id: str
    user_id: str
    type: str
    parameters: List[ActionParameter] = field(default_factory=list)


@dataclass
class AddActionRequest(Request):

    args: AddActionRequestArgs
    request: str = field(default=wo_suffix(__qualname__), init=False)  # type: ignore  # noqa: F821


@dataclass
class AddActionResponse(Response):

    response: str = field(default=AddActionRequest.request, init=False)


# ----------------------------------------------------------------------------------------------------------------------


@dataclass
class UpdateActionRequestArgs(JsonSchemaMixin):

    action_id: str
    parameters: List[ActionParameter] = field(default_factory=list)


@dataclass
class UpdateActionRequest(Request):

    args: UpdateActionRequestArgs
    request: str = field(default=wo_suffix(__qualname__), init=False)  # type: ignore  # noqa: F821


@dataclass
class UpdateActionResponse(Response):

    response: str = field(default=UpdateActionRequest.request, init=False)


# ----------------------------------------------------------------------------------------------------------------------


@dataclass
class RemoveActionRequest(Request):

    args: IdArgs
    request: str = field(default=wo_suffix(__qualname__), init=False)  # type: ignore  # noqa: F821


@dataclass
class RemoveActionResponse(Response):

    response: str = field(default=RemoveActionRequest.request, init=False)

# ----------------------------------------------------------------------------------------------------------------------


@dataclass
class UpdateActionLogicArgs(JsonSchemaMixin):

    action_id: str
    inputs: List[ActionIO] = field(default_factory=list)
    outputs: List[ActionIO] = field(default_factory=list)


@dataclass
class UpdateActionLogicRequest(Request):

    args: UpdateActionLogicArgs
    request: str = field(default=wo_suffix(__qualname__), init=False)  # type: ignore  # noqa: F821


@dataclass
class UpdateActionLogicResponse(Response):

    response: str = field(default=UpdateActionLogicRequest.request, init=False)

# ----------------------------------------------------------------------------------------------------------------------


@dataclass
class UpdateActionPointJointsRequestArgs(IdArgs):

    robot_id: str
    joints_id: str = "default"


@dataclass
class UpdateActionPointJointsRequest(Request):

    args: UpdateActionPointJointsRequestArgs
    request: str = field(default=wo_suffix(__qualname__), init=False)  # type: ignore  # noqa: F821


@dataclass
class UpdateActionPointJointsResponse(Response):

    response: str = field(default=UpdateActionPointJointsRequest.request, init=False)

# ----------------------------------------------------------------------------------------------------------------------


@dataclass
class RemoveActionPointJointsRequestArgs(JsonSchemaMixin):

    action_point_id: str
    joints_id: str


@dataclass
class RemoveActionPointJointsRequest(Request):

    args: RemoveActionPointJointsRequestArgs
    request: str = field(default=wo_suffix(__qualname__), init=False)  # type: ignore  # noqa: F821


@dataclass
class RemoveActionPointJointsResponse(Response):

    response: str = field(default=RemoveActionPointJointsRequest.request, init=False)
