# -*- coding: utf-8 -*-

from typing import List, Set

from dataclasses import dataclass, field
from dataclasses_jsonschema import JsonSchemaMixin

from arcor2.data.common import IdDesc, SceneObject, SceneService
from arcor2.data.rpc.common import IdArgs, Request, Response, wo_suffix, TypeArgs


@dataclass
class SceneObjectUsageRequest(Request):

    args: IdArgs = field(metadata=dict(description="ID could be object or service."))
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
class ListScenesRequest(Request):

    request: str = field(default=wo_suffix(__qualname__), init=False)  # type: ignore  # noqa: F821


@dataclass
class ListScenesResponse(Response):

    data: List[IdDesc] = field(default_factory=list)
    response: str = field(default=ListScenesRequest.request, init=False)

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
