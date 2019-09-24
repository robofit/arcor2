# -*- coding: utf-8 -*-

from typing import List, Optional, Tuple

from dataclasses import dataclass, field
from dataclasses_jsonschema import JsonSchemaMixin

from arcor2.data.common import IdDesc, ProjectState, ActionState, CurrentAction
from arcor2.data.object_type import ObjectTypeMeta, MeshList, ObjectActions

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
    id: str
    end_effector: str

    def as_tuple(self) -> Tuple[str, str]:
        return self.id, self.end_effector


"""
------------------------------------------------------------------------------------------------------------------------
Objects
------------------------------------------------------------------------------------------------------------------------
"""


@dataclass
class GetObjectTypesRequest(Request):

    request: str = field(default="getObjectTypes", init=False)


@dataclass
class GetObjectTypesResponse(Response):

    data: List[ObjectTypeMeta] = field(default_factory=list)
    response: str = field(default=GetObjectTypesRequest.request, init=False)


# ----------------------------------------------------------------------------------------------------------------------


@dataclass
class GetObjectActionsRequest(Request):

    args: TypeArgs
    request: str = field(default="getObjectActions", init=False)


@dataclass
class GetObjectActionsResponse(Response):

    data: ObjectActions = field(default_factory=list)
    response: str = field(default=GetObjectActionsRequest.request, init=False)


# ----------------------------------------------------------------------------------------------------------------------


@dataclass
class NewObjectTypeRequest(Request):

    args: ObjectTypeMeta
    request: str = field(default="newObjectType", init=False)


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
    request: str = field(default="focusObjectStart", init=False)


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
    request: str = field(default="focusObject", init=False)


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
    request: str = field(default="focusObjectDone", init=False)


@dataclass
class FocusObjectDoneResponse(Response):

    data: FocusObjectResponseData = field(default_factory=FocusObjectResponseData)
    response: str = field(default=FocusObjectDoneRequest.request, init=False)


# ----------------------------------------------------------------------------------------------------------------------


@dataclass
class UpdateActionPointPoseRequestArgs(IdArgs):

    robot: RobotArg


@dataclass
class UpdateActionPointPoseRequest(Request):

    args: UpdateActionPointPoseRequestArgs
    request: str = field(default="focusObjectDone", init=False)


@dataclass
class UpdateActionPointPoseResponse(Response):

    response: str = field(default=UpdateActionPointPoseRequest.request, init=False)


# ----------------------------------------------------------------------------------------------------------------------


@dataclass
class UpdateActionObjectPoseRequestArgs(IdArgs):

    robot: RobotArg


@dataclass
class UpdateActionObjectPoseRequest(Request):

    args: UpdateActionObjectPoseRequestArgs
    request: str = field(default="updateActionObjectPose", init=False)


@dataclass
class UpdateActionObjectPoseResponse(Response):

    response: str = field(default=UpdateActionObjectPoseRequest.request, init=False)


"""
------------------------------------------------------------------------------------------------------------------------
Scene / project
------------------------------------------------------------------------------------------------------------------------
"""


@dataclass
class SaveSceneRequest(Request):

    request: str = field(default="saveScene", init=False)


@dataclass
class SaveSceneResponse(Response):

    response: str = field(default=SaveSceneRequest.request, init=False)


# ----------------------------------------------------------------------------------------------------------------------


@dataclass
class SaveProjectRequest(Request):

    request: str = field(default="saveProject", init=False)


@dataclass
class SaveProjectResponse(Response):

    response: str = field(default=SaveProjectRequest.request, init=False)


# ----------------------------------------------------------------------------------------------------------------------


@dataclass
class OpenProjectRequest(Request):

    args: IdArgs
    request: str = field(default="openProject", init=False)


@dataclass
class OpenProjectResponse(Response):

    response: str = field(default=OpenProjectRequest.request, init=False)


# ----------------------------------------------------------------------------------------------------------------------


@dataclass
class ListProjectsRequest(Request):

    request: str = field(default="listProjects", init=False)


@dataclass
class ListProjectsResponse(Response):

    data: List[IdDesc] = field(default_factory=list)
    response: str = field(default=ListProjectsRequest.request, init=False)


# ----------------------------------------------------------------------------------------------------------------------


@dataclass
class ListScenesRequest(Request):

    request: str = field(default="listScenes", init=False)


@dataclass
class ListScenesResponse(Response):

    data: List[IdDesc] = field(default_factory=list)
    response: str = field(default=ListScenesRequest.request, init=False)


# ----------------------------------------------------------------------------------------------------------------------


@dataclass
class RunProjectRequest(Request):

    args: IdArgs
    request: str = field(default="runProject", init=False)


@dataclass
class RunProjectResponse(Response):

    response: str = field(default=RunProjectRequest.request, init=False)


# ----------------------------------------------------------------------------------------------------------------------


@dataclass
class StopProjectRequest(Request):

    request: str = field(default="stopProject", init=False)


@dataclass
class StopProjectResponse(Response):

    response: str = field(default=StopProjectRequest.request, init=False)


# ----------------------------------------------------------------------------------------------------------------------


@dataclass
class PauseProjectRequest(Request):

    request: str = field(default="pauseProject", init=False)


@dataclass
class PauseProjectResponse(Response):

    response: str = field(default=PauseProjectRequest.request, init=False)


# ----------------------------------------------------------------------------------------------------------------------

@dataclass
class ProjectStateRequest(Request):

    request: str = field(default="projectState", init=False)


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

    request: str = field(default="resumeProject", init=False)


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

    request: str = field(default="listMeshes", init=False)


@dataclass
class ListMeshesResponse(Response):

    data: MeshList = field(default_factory=list)
    response: str = field(default=ListMeshesRequest.request, init=False)
