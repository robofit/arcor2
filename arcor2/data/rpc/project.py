# -*- coding: utf-8 -*-

from typing import List, Optional

from dataclasses import dataclass, field
from dataclasses_jsonschema import JsonSchemaMixin

from arcor2.data.common import IdDesc, Position, ActionParameter, ActionIO, Orientation
from arcor2.data.rpc.common import IdArgs, Request, Response, wo_suffix, RobotArg


@dataclass
class NewProjectRequestArgs(JsonSchemaMixin):

    scene_id: str
    name: str
    desc: str = field(default_factory=str)
    has_logic: bool = True


@dataclass
class NewProjectRequest(Request):

    args: NewProjectRequestArgs
    dry_run: bool = False
    request: str = field(default=wo_suffix(__qualname__), init=False)  # type: ignore  # noqa: F821


@dataclass
class NewProjectResponse(Response):

    response: str = field(default=NewProjectRequest.request, init=False)

# ----------------------------------------------------------------------------------------------------------------------


@dataclass
class CloseProjectRequestArgs(JsonSchemaMixin):

    force: bool = False


@dataclass
class CloseProjectRequest(Request):

    args: CloseProjectRequestArgs
    dry_run: bool = False
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

    name: str = field(default_factory=str)
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
class CancelActionRequest(Request):

    request: str = field(default=wo_suffix(__qualname__), init=False)  # type: ignore  # noqa: F821


@dataclass
class CancelActionResponse(Response):

    response: str = field(default=CancelActionRequest.request, init=False)

# ----------------------------------------------------------------------------------------------------------------------


@dataclass
class AddActionPointArgs(JsonSchemaMixin):

    name: str
    position: Position
    parent: Optional[str] = None


@dataclass
class AddActionPointRequest(Request):

    args: AddActionPointArgs
    dry_run: bool = False
    request: str = field(default=wo_suffix(__qualname__), init=False)  # type: ignore  # noqa: F821


@dataclass
class AddActionPointResponse(Response):

    response: str = field(default=AddActionPointRequest.request, init=False)

# ----------------------------------------------------------------------------------------------------------------------


@dataclass
class RemoveActionPointRequest(Request):

    args: IdArgs
    dry_run: bool = False
    request: str = field(default=wo_suffix(__qualname__), init=False)  # type: ignore  # noqa: F821


@dataclass
class RemoveActionPointResponse(Response):

    response: str = field(default=RemoveActionPointRequest.request, init=False)

# ----------------------------------------------------------------------------------------------------------------------


@dataclass
class AddActionPointJointsRequestArgs(JsonSchemaMixin):

    action_point_id: str
    robot_id: str
    name: str = "default"


@dataclass
class AddActionPointJointsRequest(Request):

    args: AddActionPointJointsRequestArgs
    dry_run: bool = False
    request: str = field(default=wo_suffix(__qualname__), init=False)  # type: ignore  # noqa: F821


@dataclass
class AddActionPointJointsResponse(Response):

    response: str = field(default=AddActionPointJointsRequest.request, init=False)

# ----------------------------------------------------------------------------------------------------------------------


@dataclass
class RenameActionPointRequestArgs(JsonSchemaMixin):

    action_point_id: str
    new_name: str


@dataclass
class RenameActionPointRequest(Request):

    args: RenameActionPointRequestArgs
    dry_run: bool = False
    request: str = field(default=wo_suffix(__qualname__), init=False)  # type: ignore  # noqa: F821


@dataclass
class RenameActionPointResponse(Response):

    response: str = field(default=RenameActionPointRequest.request, init=False)


# ----------------------------------------------------------------------------------------------------------------------


@dataclass
class UpdateActionPointParentRequestArgs(JsonSchemaMixin):

    action_point_id: str
    new_parent_id: str


@dataclass
class UpdateActionPointParentRequest(Request):

    args: UpdateActionPointParentRequestArgs
    request: str = field(default=wo_suffix(__qualname__), init=False)  # type: ignore  # noqa: F821


@dataclass
class UpdateActionPointParentResponse(Response):

    response: str = field(default=UpdateActionPointParentRequest.request, init=False)


# ----------------------------------------------------------------------------------------------------------------------


@dataclass
class UpdateActionPointPositionRequestArgs(JsonSchemaMixin):

    action_point_id: str
    new_position: Position


@dataclass
class UpdateActionPointPositionRequest(Request):

    args: UpdateActionPointPositionRequestArgs
    request: str = field(default=wo_suffix(__qualname__), init=False)  # type: ignore  # noqa: F821


@dataclass
class UpdateActionPointPositionResponse(Response):

    response: str = field(default=UpdateActionPointPositionRequest.request, init=False)

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
    name: str = "default"


@dataclass
class AddActionPointOrientationUsingRobotRequest(Request):

    args: AddActionPointOrientationUsingRobotRequestArgs
    dry_run: bool = False
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
    name: str = "default"


@dataclass
class AddActionPointOrientationRequest(Request):

    args: AddActionPointOrientationRequestArgs
    dry_run: bool = False
    request: str = field(default=wo_suffix(__qualname__), init=False)  # type: ignore  # noqa: F821


@dataclass
class AddActionPointOrientationResponse(Response):

    response: str = field(default=AddActionPointOrientationRequest.request, init=False)

# ----------------------------------------------------------------------------------------------------------------------


@dataclass
class UpdateActionPointOrientationRequestArgs(JsonSchemaMixin):

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
    dry_run: bool = False
    request: str = field(default=wo_suffix(__qualname__), init=False)  # type: ignore  # noqa: F821


@dataclass
class RemoveActionPointOrientationResponse(Response):
    response: str = field(default=RemoveActionPointOrientationRequest.request, init=False)

# ----------------------------------------------------------------------------------------------------------------------


@dataclass
class AddActionRequestArgs(JsonSchemaMixin):

    action_point_id: str
    name: str
    type: str
    parameters: List[ActionParameter] = field(default_factory=list)


@dataclass
class AddActionRequest(Request):

    args: AddActionRequestArgs
    dry_run: bool = False
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
    dry_run: bool = False
    request: str = field(default=wo_suffix(__qualname__), init=False)  # type: ignore  # noqa: F821


@dataclass
class UpdateActionResponse(Response):

    response: str = field(default=UpdateActionRequest.request, init=False)


# ----------------------------------------------------------------------------------------------------------------------


@dataclass
class RemoveActionRequest(Request):

    args: IdArgs
    dry_run: bool = False
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
class UpdateActionPointJointsRequestArgs(JsonSchemaMixin):

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

    joints_id: str


@dataclass
class RemoveActionPointJointsRequest(Request):

    args: RemoveActionPointJointsRequestArgs
    request: str = field(default=wo_suffix(__qualname__), init=False)  # type: ignore  # noqa: F821


@dataclass
class RemoveActionPointJointsResponse(Response):

    response: str = field(default=RemoveActionPointJointsRequest.request, init=False)

# ----------------------------------------------------------------------------------------------------------------------


@dataclass
class DeleteProjectRequest(Request):

    args: IdArgs
    request: str = field(default=wo_suffix(__qualname__), init=False)  # type: ignore  # noqa: F821


@dataclass
class DeleteProjectResponse(Response):

    response: str = field(default=DeleteProjectRequest.request, init=False)

# ----------------------------------------------------------------------------------------------------------------------


@dataclass
class RenameProjectRequestArgs(JsonSchemaMixin):

    project_id: str
    new_name: str


@dataclass
class RenameProjectRequest(Request):

    args: RenameProjectRequestArgs
    dry_run: bool = False
    request: str = field(default=wo_suffix(__qualname__), init=False)  # type: ignore  # noqa: F821


@dataclass
class RenameProjectResponse(Response):

    response: str = field(default=RenameProjectRequest.request, init=False)

# ----------------------------------------------------------------------------------------------------------------------


@dataclass
class CopyProjectRequestArgs(JsonSchemaMixin):

    source_id: str
    target_name: str


@dataclass
class CopyProjectRequest(Request):

    args: CopyProjectRequestArgs
    dry_run: bool = False
    request: str = field(default=wo_suffix(__qualname__), init=False)  # type: ignore  # noqa: F821


@dataclass
class CopyProjectResponse(Response):

    response: str = field(default=CopyProjectRequest.request, init=False)

# ----------------------------------------------------------------------------------------------------------------------


@dataclass
class UpdateProjectDescriptionRequestArgs(JsonSchemaMixin):

    project_id: str
    new_description: str


@dataclass
class UpdateProjectDescriptionRequest(Request):

    args: UpdateProjectDescriptionRequestArgs
    request: str = field(default=wo_suffix(__qualname__), init=False)  # type: ignore  # noqa: F821


@dataclass
class UpdateProjectDescriptionResponse(Response):

    response: str = field(default=UpdateProjectDescriptionRequest.request, init=False)

# ----------------------------------------------------------------------------------------------------------------------


@dataclass
class UpdateProjectHasLogicRequestArgs(JsonSchemaMixin):

    project_id: str
    new_has_logic: bool


@dataclass
class UpdateProjectHasLogicRequest(Request):

    args: UpdateProjectHasLogicRequestArgs
    request: str = field(default=wo_suffix(__qualname__), init=False)  # type: ignore  # noqa: F821


@dataclass
class UpdateProjectHasLogicResponse(Response):

    response: str = field(default=UpdateProjectHasLogicRequest.request, init=False)

# ----------------------------------------------------------------------------------------------------------------------


@dataclass
class RenameActionPointJointsRequestArgs(JsonSchemaMixin):

    joints_id: str
    new_name: str


@dataclass
class RenameActionPointJointsRequest(Request):

    args: RenameActionPointJointsRequestArgs
    dry_run: bool = False
    request: str = field(default=wo_suffix(__qualname__), init=False)  # type: ignore  # noqa: F821


@dataclass
class RenameActionPointJointsResponse(Response):

    response: str = field(default=RenameActionPointJointsRequest.request, init=False)

# ----------------------------------------------------------------------------------------------------------------------


@dataclass
class RenameActionPointOrientationRequestArgs(JsonSchemaMixin):

    orientation_id: str
    new_name: str


@dataclass
class RenameActionPointOrientationRequest(Request):

    args: RenameActionPointOrientationRequestArgs
    dry_run: bool = False
    request: str = field(default=wo_suffix(__qualname__), init=False)  # type: ignore  # noqa: F821


@dataclass
class RenameActionPointOrientationResponse(Response):

    response: str = field(default=RenameActionPointOrientationRequest.request, init=False)

# ----------------------------------------------------------------------------------------------------------------------


@dataclass
class RenameActionRequestArgs(JsonSchemaMixin):

    action_id: str
    new_name: str


@dataclass
class RenameActionRequest(Request):

    args: RenameActionRequestArgs
    dry_run: bool = False
    request: str = field(default=wo_suffix(__qualname__), init=False)  # type: ignore  # noqa: F821


@dataclass
class RenameActionResponse(Response):

    response: str = field(default=RenameActionRequest.request, init=False)
