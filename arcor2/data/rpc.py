# -*- coding: utf-8 -*-

from typing import List, Optional, Tuple, Set
import re

from dataclasses import dataclass, field
from dataclasses_jsonschema import JsonSchemaMixin

from arcor2.data.common import IdDesc, ProjectState, ActionState, CurrentAction, SceneObject, SceneService, \
    IdValue
from arcor2.data.object_type import ObjectTypeMeta, MeshList, ObjectActions
from arcor2.data.services import ServiceTypeMeta
from arcor2.data.robot import RobotMeta

"""
mypy does not recognize __qualname__ so far: https://github.com/python/mypy/issues/6473
flake8 sucks here as well: https://bugs.launchpad.net/pyflakes/+bug/1648651
TODO: remove type: ignore once it is fixed
"""


def wo_suffix(name: str) -> str:
    return re.sub('Request$', '', name)


"""
------------------------------------------------------------------------------------------------------------------------
Common stuff
------------------------------------------------------------------------------------------------------------------------
"""


@dataclass
class Request(JsonSchemaMixin):

    id: int
    request: str


@dataclass
class Response(JsonSchemaMixin):

    response: str = ""
    id: int = 0
    result: bool = True
    messages: Optional[List[str]] = None


# ----------------------------------------------------------------------------------------------------------------------

@dataclass
class TypeArgs(JsonSchemaMixin):
    type: str


@dataclass
class IdArgs(JsonSchemaMixin):
    id: str


@dataclass
class RobotArg(JsonSchemaMixin):
    robot_id: str  # object id of the robot or robot_id within the robot service
    end_effector: str

    def as_tuple(self) -> Tuple[str, str]:
        return self.robot_id, self.end_effector


"""
------------------------------------------------------------------------------------------------------------------------
Services
------------------------------------------------------------------------------------------------------------------------
"""


@dataclass
class GetServicesRequest(Request):

    request: str = field(default=wo_suffix(__qualname__), init=False)  # type: ignore  # noqa: F821


@dataclass
class GetServicesResponse(Response):

    data: List[ServiceTypeMeta] = field(default_factory=list)
    response: str = field(default=GetServicesRequest.request, init=False)


"""
------------------------------------------------------------------------------------------------------------------------
Objects
------------------------------------------------------------------------------------------------------------------------
"""


@dataclass
class ActionParamValuesArgs(JsonSchemaMixin):

    id: str  # object or service id
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


@dataclass
class UpdateActionPointPoseRequestArgs(IdArgs):

    robot: RobotArg
    update_position: bool
    orientation_id: str = "default"


@dataclass
class UpdateActionPointPoseRequest(Request):

    args: UpdateActionPointPoseRequestArgs
    request: str = field(default=wo_suffix(__qualname__), init=False)  # type: ignore  # noqa: F821


@dataclass
class UpdateActionPointPoseResponse(Response):

    response: str = field(default=UpdateActionPointPoseRequest.request, init=False)


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
class UpdateActionObjectPoseRequestArgs(IdArgs):

    robot: RobotArg


@dataclass
class UpdateActionObjectPoseRequest(Request):

    args: UpdateActionObjectPoseRequestArgs
    request: str = field(default=wo_suffix(__qualname__), init=False)  # type: ignore  # noqa: F821


@dataclass
class UpdateActionObjectPoseResponse(Response):

    response: str = field(default=UpdateActionObjectPoseRequest.request, init=False)


"""
------------------------------------------------------------------------------------------------------------------------
Scene / project
------------------------------------------------------------------------------------------------------------------------
"""


@dataclass
class SceneObjectUsageRequest(Request):

    args: IdArgs  # ID could be object or service
    request: str = field(default=wo_suffix(__qualname__), init=False)  # type: ignore  # noqa: F821


@dataclass
class SceneObjectUsageResponse(Response):

    data: Set[str] = field(default_factory=set)
    response: str = field(default=SceneObjectUsageRequest.request, init=False)


# ----------------------------------------------------------------------------------------------------------------------


@dataclass
class AutoAddObjectToSceneRequest(Request):

    args: TypeArgs
    request: str = field(default=wo_suffix(__qualname__), init=False)  # type: ignore  # noqa: F821


@dataclass
class AutoAddObjectToSceneResponse(Response):

    response: str = field(default=AutoAddObjectToSceneRequest.request, init=False)


# ----------------------------------------------------------------------------------------------------------------------

@dataclass
class AddObjectToSceneRequest(Request):

    args: SceneObject
    request: str = field(default=wo_suffix(__qualname__), init=False)  # type: ignore  # noqa: F821


@dataclass
class AddObjectToSceneResponse(Response):

    response: str = field(default=AddObjectToSceneRequest.request, init=False)

# ----------------------------------------------------------------------------------------------------------------------


@dataclass
class AddServiceToSceneRequest(Request):

    args: SceneService
    request: str = field(default=wo_suffix(__qualname__), init=False)  # type: ignore  # noqa: F821


@dataclass
class AddServiceToSceneResponse(Response):

    response: str = field(default=AddServiceToSceneRequest.request, init=False)

# ----------------------------------------------------------------------------------------------------------------------


@dataclass
class RemoveFromSceneRequest(Request):

    args: IdArgs
    request: str = field(default=wo_suffix(__qualname__), init=False)  # type: ignore  # noqa: F821


@dataclass
class RemoveFromSceneResponse(Response):
    response: str = field(default=RemoveFromSceneRequest.request, init=False)


# ----------------------------------------------------------------------------------------------------------------------


@dataclass
class SaveSceneRequest(Request):

    request: str = field(default=wo_suffix(__qualname__), init=False)  # type: ignore  # noqa: F821


@dataclass
class SaveSceneResponse(Response):

    response: str = field(default=SaveSceneRequest.request, init=False)


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
class OpenSceneRequest(Request):

    args: IdArgs
    request: str = field(default=wo_suffix(__qualname__), init=False)  # type: ignore  # noqa: F821


@dataclass
class OpenSceneResponse(Response):

    response: str = field(default=OpenSceneRequest.request, init=False)

# ----------------------------------------------------------------------------------------------------------------------


@dataclass
class ListProjectsResponseData(IdDesc):

    valid: bool = False  # objects and their actions exists
    executable: bool = False  # logic is defined and valid
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
class ListScenesRequest(Request):

    request: str = field(default=wo_suffix(__qualname__), init=False)  # type: ignore  # noqa: F821


@dataclass
class ListScenesResponse(Response):

    data: List[IdDesc] = field(default_factory=list)
    response: str = field(default=ListScenesRequest.request, init=False)


# ----------------------------------------------------------------------------------------------------------------------


@dataclass
class RunProjectRequest(Request):

    args: IdArgs
    request: str = field(default=wo_suffix(__qualname__), init=False)  # type: ignore  # noqa: F821


@dataclass
class RunProjectResponse(Response):

    response: str = field(default=RunProjectRequest.request, init=False)


# ----------------------------------------------------------------------------------------------------------------------


@dataclass
class StopProjectRequest(Request):

    request: str = field(default=wo_suffix(__qualname__), init=False)  # type: ignore  # noqa: F821


@dataclass
class StopProjectResponse(Response):

    response: str = field(default=StopProjectRequest.request, init=False)


# ----------------------------------------------------------------------------------------------------------------------


@dataclass
class PauseProjectRequest(Request):

    request: str = field(default=wo_suffix(__qualname__), init=False)  # type: ignore  # noqa: F821


@dataclass
class PauseProjectResponse(Response):

    response: str = field(default=PauseProjectRequest.request, init=False)


# ----------------------------------------------------------------------------------------------------------------------

@dataclass
class ProjectStateRequest(Request):

    request: str = field(default=wo_suffix(__qualname__), init=False)  # type: ignore  # noqa: F821


@dataclass
class ProjectStateData(JsonSchemaMixin):

    id: Optional[str] = None
    project: ProjectState = field(default_factory=ProjectState)
    action: Optional[ActionState] = None
    action_args: Optional[CurrentAction] = None


@dataclass
class ProjectStateResponse(Response):

    data: ProjectStateData = field(default_factory=ProjectStateData)
    response: str = field(default=ProjectStateRequest.request, init=False)


# ----------------------------------------------------------------------------------------------------------------------


@dataclass
class ResumeProjectRequest(Request):

    request: str = field(default=wo_suffix(__qualname__), init=False)  # type: ignore  # noqa: F821


@dataclass
class ResumeProjectResponse(Response):

    response: str = field(default=ResumeProjectRequest.request, init=False)


# ----------------------------------------------------------------------------------------------------------------------


"""
------------------------------------------------------------------------------------------------------------------------
Storage / data
------------------------------------------------------------------------------------------------------------------------
"""


@dataclass
class ListMeshesRequest(Request):

    request: str = field(default=wo_suffix(__qualname__), init=False)  # type: ignore  # noqa: F821


@dataclass
class ListMeshesResponse(Response):

    data: MeshList = field(default_factory=list)
    response: str = field(default=ListMeshesRequest.request, init=False)


"""
------------------------------------------------------------------------------------------------------------------------
Robot object type / service
------------------------------------------------------------------------------------------------------------------------
"""


@dataclass
class GetRobotMetaRequest(Request):

    request: str = field(default=wo_suffix(__qualname__), init=False)  # type: ignore  # noqa: F821


@dataclass
class GetRobotMetaResponse(Response):

    data: List[RobotMeta] = field(default_factory=list)
    response: str = field(default=GetRobotMetaRequest.request, init=False)
