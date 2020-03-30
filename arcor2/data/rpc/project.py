# -*- coding: utf-8 -*-

from typing import List, Optional

from dataclasses import dataclass, field
from dataclasses_jsonschema import JsonSchemaMixin

from arcor2.data.common import IdDesc, Position
from arcor2.data.rpc.common import IdArgs, Request, Response, wo_suffix


@dataclass
class NewProjectRequestArgs(JsonSchemaMixin):

    scene_id: str
    user_id: str
    desc: str = field(default_factory=str)


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
