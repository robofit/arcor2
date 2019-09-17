# -*- coding: utf-8 -*-

from typing import Dict, List, Optional, Tuple, Type
from typing_extensions import Literal, Final

from dataclasses import dataclass, field
from dataclasses_jsonschema import JsonSchemaMixin

from arcor2.data.common import IdDesc
from arcor2.data.object_type import ObjectTypeMeta, MeshList, ObjectActions

"""
------------------------------------------------------------------------------------------------------------------------
Common stuff
------------------------------------------------------------------------------------------------------------------------
"""


@dataclass
class Request(JsonSchemaMixin):

    id: int


@dataclass
class Response(JsonSchemaMixin):

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


API_MAPPING: Dict[str, Tuple[Type[Request], Type[Response]]] = {}

"""
------------------------------------------------------------------------------------------------------------------------
Objects
------------------------------------------------------------------------------------------------------------------------
"""


@dataclass
class GetObjectTypesRequest(Request):

    request: Final[str] = "getObjectTypes"


@dataclass
class GetObjectTypesResponse(Response):

    response: Final[str] = "getObjectTypes"
    data: List[ObjectTypeMeta] = field(default_factory=list)


API_MAPPING["getObjectTypes"] = (GetObjectTypesRequest, GetObjectTypesResponse)

# ----------------------------------------------------------------------------------------------------------------------


@dataclass
class GetObjectActionsRequest(Request):

    args: TypeArgs
    request: Final[str] = "getObjectActions"


@dataclass
class GetObjectActionsResponse(Response):

    response: Final[str] = "getObjectActions"
    data: ObjectActions = field(default_factory=list)


API_MAPPING["getObjectActions"] = (GetObjectActionsRequest, GetObjectActionsResponse)

# ----------------------------------------------------------------------------------------------------------------------


@dataclass
class NewObjectTypeRequest(Request):

    args: ObjectTypeMeta
    request: Final[str] = "newObjectType"


@dataclass
class NewObjectTypeResponse(Response):

    response: Final[str] = "newObjectType"


API_MAPPING["newObjectType"] = (NewObjectTypeRequest, NewObjectTypeResponse)

# ----------------------------------------------------------------------------------------------------------------------


@dataclass
class FocusObjectStartRequestArgs(JsonSchemaMixin):

    object_id: str
    robot: RobotArg


@dataclass
class FocusObjectStartRequest(Request):

    args: FocusObjectStartRequestArgs
    request: Final[str] = "focusObjectStart"


@dataclass
class FocusObjectStartResponse(Response):

    response: Final[str] = "focusObjectStart"


API_MAPPING["focusObjectStart"] = (FocusObjectStartRequest, FocusObjectStartResponse)

# ----------------------------------------------------------------------------------------------------------------------


@dataclass
class FocusObjectRequestArgs(JsonSchemaMixin):

    object_id: str
    point_idx: int


@dataclass
class FocusObjectRequest(Request):

    args: FocusObjectRequestArgs
    request: Final[str] = "focusObject"


@dataclass
class FocusObjectResponseData(JsonSchemaMixin):

    finished_indexes: List[int] = field(default_factory=list)


@dataclass
class FocusObjectResponse(Response):

    response: Final[str] = "focusObject"
    data: FocusObjectResponseData = field(default_factory=FocusObjectResponseData)


API_MAPPING["focusObject"] = (FocusObjectRequest, FocusObjectResponse)

# ----------------------------------------------------------------------------------------------------------------------


@dataclass
class FocusObjectDoneRequest(Request):

    args: IdArgs
    request: Final[str] = "focusObjectDone"


@dataclass
class FocusObjectDoneResponse(Response):

    response: Final[str] = "focusObjectDone"
    data: FocusObjectResponseData = field(default_factory=FocusObjectResponseData)


API_MAPPING["focusObjectDone"] = (FocusObjectDoneRequest, FocusObjectDoneResponse)


# ----------------------------------------------------------------------------------------------------------------------


@dataclass
class UpdateActionPointPoseRequestArgs(IdArgs):

    robot: RobotArg


@dataclass
class UpdateActionPointPoseRequest(Request):

    args: UpdateActionPointPoseRequestArgs
    request: Final[str] = "updateActionPointPose"


@dataclass
class UpdateActionPointPoseResponse(Response):

    response: Final[str] = "updateActionPointPose"


API_MAPPING["updateActionPointPose"] = (UpdateActionPointPoseRequest, UpdateActionPointPoseResponse)


# ----------------------------------------------------------------------------------------------------------------------


@dataclass
class UpdateActionObjectPoseRequestArgs(IdArgs):

    robot: RobotArg


@dataclass
class UpdateActionObjectPoseRequest(Request):

    args: UpdateActionObjectPoseRequestArgs
    request: Final[str] = "updateActionObjectPose"


@dataclass
class UpdateActionObjectPoseResponse(Response):

    response: Final[str] = "updateActionObjectPose"


API_MAPPING["updateActionObjectPose"] = (UpdateActionPointPoseRequest, UpdateActionPointPoseResponse)


"""
------------------------------------------------------------------------------------------------------------------------
Scene / project
------------------------------------------------------------------------------------------------------------------------
"""


@dataclass
class SaveSceneRequest(Request):

    request: Final[str] = "saveScene"


@dataclass
class SaveSceneResponse(Response):

    response: Final[str] = "saveScene"


API_MAPPING["saveScene"] = (SaveSceneRequest, SaveSceneResponse)

# ----------------------------------------------------------------------------------------------------------------------


@dataclass
class SaveProjectRequest(Request):

    request: Final[str] = "saveProject"


@dataclass
class SaveProjectResponse(Response):

    response: Final[str] = "saveProject"


API_MAPPING["saveProject"] = (SaveProjectRequest, SaveProjectResponse)

# ----------------------------------------------------------------------------------------------------------------------


@dataclass
class OpenProjectRequest(Request):

    args: IdArgs
    request: Final[str] = "openProject"


@dataclass
class OpenProjectResponse(Response):

    response: Final[str] = "openProject"


API_MAPPING["openProject"] = (OpenProjectRequest, OpenProjectResponse)

# ----------------------------------------------------------------------------------------------------------------------


@dataclass
class ListProjectsRequest(Request):

    request: Literal["listProjects"]


@dataclass
class ListProjectsResponse(Response):

    response: Final[str] = "listProjects"
    data: List[IdDesc] = field(default_factory=list)


API_MAPPING["listProjects"] = (ListProjectsRequest, ListProjectsResponse)

# ----------------------------------------------------------------------------------------------------------------------


@dataclass
class ListScenesRequest(Request):

    request: Final[str] = "listScenes"


@dataclass
class ListScenesResponse(Response):

    response: Final[str] = "listScenes"
    data: List[IdDesc] = field(default_factory=list)


API_MAPPING["listScenes"] = (ListScenesRequest, ListScenesResponse)

# ----------------------------------------------------------------------------------------------------------------------


@dataclass
class RunProjectRequest(Request):

    args: IdArgs
    request: Final[str] = "runProject"


@dataclass
class RunProjectResponse(Response):

    response: Final[str] = "runProject"


API_MAPPING["runProject"] = (RunProjectRequest, RunProjectResponse)

# ----------------------------------------------------------------------------------------------------------------------


@dataclass
class StopProjectRequest(Request):

    request: Final[str] = "stopProject"


@dataclass
class StopProjectResponse(Response):

    response: Final[str] = "stopProject"


API_MAPPING["stopProject"] = (StopProjectRequest, StopProjectResponse)

# ----------------------------------------------------------------------------------------------------------------------


@dataclass
class PauseProjectRequest(Request):

    request: Final[str] = "pauseProject"


@dataclass
class PauseProjectResponse(Response):

    response: Final[str] = "pauseProject"


API_MAPPING["pauseProject"] = (PauseProjectRequest, PauseProjectResponse)

# ----------------------------------------------------------------------------------------------------------------------


@dataclass
class ResumeProjectRequest(Request):

    request: Final[str] = "resumeProject"


@dataclass
class ResumeProjectResponse(Response):

    response: Final[str] = "resumeProject"


API_MAPPING["resumeProject"] = (ResumeProjectRequest, ResumeProjectResponse)

# ----------------------------------------------------------------------------------------------------------------------


"""
------------------------------------------------------------------------------------------------------------------------
Storage / data
------------------------------------------------------------------------------------------------------------------------
"""


@dataclass
class ListMeshesRequest(Request):

    request: Final[str] = "listMeshes"


@dataclass
class ListMeshesResponse(Response):

    response: Final[str] = "listMeshes"
    data: MeshList = field(default_factory=list)


API_MAPPING["listMeshes"] = (ListMeshesRequest, ListMeshesResponse)
