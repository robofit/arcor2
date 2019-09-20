# -*- coding: utf-8 -*-

from typing import Dict, List, Optional, Tuple, Type
from typing_extensions import Literal, Final
import inspect
import sys

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
    request: str


@dataclass
class Response(JsonSchemaMixin):

    response: str
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

    request: Final[str] = "getObjectTypes"


@dataclass
class GetObjectTypesResponse(Response):

    response: Final[str] = GetObjectTypesRequest.request
    data: List[ObjectTypeMeta] = field(default_factory=list)


# ----------------------------------------------------------------------------------------------------------------------


@dataclass
class GetObjectActionsRequest(Request):

    args: TypeArgs
    request: Final[str] = "getObjectActions"


@dataclass
class GetObjectActionsResponse(Response):

    response: Final[str] = GetObjectActionsRequest.request
    data: ObjectActions = field(default_factory=list)


# ----------------------------------------------------------------------------------------------------------------------


@dataclass
class NewObjectTypeRequest(Request):

    args: ObjectTypeMeta
    request: Final[str] = "newObjectType"


@dataclass
class NewObjectTypeResponse(Response):

    response: Final[str] = NewObjectTypeRequest.request


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

    response: Final[str] = FocusObjectStartRequest.request


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

    response: Final[str] = FocusObjectRequest.request
    data: FocusObjectResponseData = field(default_factory=FocusObjectResponseData)


# ----------------------------------------------------------------------------------------------------------------------


@dataclass
class FocusObjectDoneRequest(Request):

    args: IdArgs
    request: Final[str] = "focusObjectDone"


@dataclass
class FocusObjectDoneResponse(Response):

    response: Final[str] = FocusObjectDoneRequest.request
    data: FocusObjectResponseData = field(default_factory=FocusObjectResponseData)


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

    response: Final[str] = UpdateActionPointPoseRequest.request


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

    response: Final[str] = UpdateActionObjectPoseRequest.request


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

    response: Final[str] = SaveSceneRequest.request


# ----------------------------------------------------------------------------------------------------------------------


@dataclass
class SaveProjectRequest(Request):

    request: Final[str] = "saveProject"


@dataclass
class SaveProjectResponse(Response):

    response: Final[str] = SaveProjectRequest.request


# ----------------------------------------------------------------------------------------------------------------------


@dataclass
class OpenProjectRequest(Request):

    args: IdArgs
    request: Final[str] = "openProject"


@dataclass
class OpenProjectResponse(Response):

    response: Final[str] = OpenProjectRequest.request


# ----------------------------------------------------------------------------------------------------------------------


@dataclass
class ListProjectsRequest(Request):

    request: Final[str] = "listProjects"


@dataclass
class ListProjectsResponse(Response):

    response: Final[str] = ListProjectsRequest.request
    data: List[IdDesc] = field(default_factory=list)


# ----------------------------------------------------------------------------------------------------------------------


@dataclass
class ListScenesRequest(Request):

    request: Final[str] = "listScenes"


@dataclass
class ListScenesResponse(Response):

    response: Final[str] = ListScenesRequest.request
    data: List[IdDesc] = field(default_factory=list)


# ----------------------------------------------------------------------------------------------------------------------


@dataclass
class RunProjectRequest(Request):

    args: IdArgs
    request: Final[str] = "runProject"


@dataclass
class RunProjectResponse(Response):

    response: Final[str] = RunProjectRequest.request


# ----------------------------------------------------------------------------------------------------------------------


@dataclass
class StopProjectRequest(Request):

    request: Final[str] = "stopProject"


@dataclass
class StopProjectResponse(Response):

    response: Final[str] = StopProjectRequest.request


# ----------------------------------------------------------------------------------------------------------------------


@dataclass
class PauseProjectRequest(Request):

    request: Final[str] = "pauseProject"


@dataclass
class PauseProjectResponse(Response):

    response: Final[str] = PauseProjectRequest.request


# ----------------------------------------------------------------------------------------------------------------------


@dataclass
class ResumeProjectRequest(Request):

    request: Final[str] = "resumeProject"


@dataclass
class ResumeProjectResponse(Response):

    response: Final[str] = ResumeProjectRequest.request


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

    response: Final[str] = ListMeshesRequest.request
    data: MeshList = field(default_factory=list)


RPC_MAPPING: Dict[str, Tuple[Type[Request], Type[Response]]] = {}

for name, obj in inspect.getmembers(sys.modules[__name__]):

    requests: Dict[str, Type[Request]] = {}
    responses: Dict[str, Type[Response]] = {}

    if inspect.isclass(obj) and issubclass(obj, Request) and obj != Request:
        requests[obj.request] = obj
    elif inspect.isclass(obj) and issubclass(obj, Response) and obj != Response:
        responses[obj.response] = obj

    assert requests.keys() == responses.keys()

    for k, v in requests.items():
        RPC_MAPPING[k] = (v, responses[k])
