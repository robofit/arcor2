# -*- coding: utf-8 -*-

from typing import List, Optional
from datetime import datetime

from dataclasses import dataclass, field
from dataclasses_jsonschema import JsonSchemaMixin

from arcor2.data.common import ProjectState, ActionState, CurrentAction
from arcor2.data.rpc.common import IdArgs, Request, Response, wo_suffix


@dataclass
class BuildProjectRequest(Request):
    """
    Calls Build service to generate execution package and uploads it to the Execution service.
    """

    args: IdArgs
    request: str = field(default=wo_suffix(__qualname__), init=False)  # type: ignore  # noqa: F821


@dataclass
class BuildProjectResponse(Response):

    response: str = field(default=BuildProjectRequest.request, init=False)

# ----------------------------------------------------------------------------------------------------------------------


@dataclass
class UploadPackageArgs(JsonSchemaMixin):

    id: str = field(metadata=dict(description="Id of the execution package (so far == ID of the project)."))
    data: str = field(metadata=dict(description="Base64 encoded content of the zip file."))


@dataclass
class UploadPackageRequest(Request):

    args: UploadPackageArgs
    request: str = field(default=wo_suffix(__qualname__), init=False)  # type: ignore  # noqa: F821


@dataclass
class UploadPackageResponse(Response):

    response: str = field(default=UploadPackageRequest.request, init=False)


# ----------------------------------------------------------------------------------------------------------------------


@dataclass
class ListPackagesRequest(Request):

    request: str = field(default=wo_suffix(__qualname__), init=False)  # type: ignore  # noqa: F821


@dataclass
class ModifiedFile(JsonSchemaMixin):

    filename: str
    modified: datetime


@dataclass
class PackageSummary(JsonSchemaMixin):

    id: str
    date_time: datetime
    # modified_files: List[ModifiedFile] = field(default_factory=list)


@dataclass
class ListPackagesResponse(Response):

    data: List[PackageSummary] = field(default_factory=list)
    response: str = field(default=ListPackagesRequest.request, init=False)


# ----------------------------------------------------------------------------------------------------------------------

@dataclass
class DeletePackageRequest(Request):

    args: IdArgs
    request: str = field(default=wo_suffix(__qualname__), init=False)  # type: ignore  # noqa: F821


@dataclass
class DeletePackageResponse(Response):

    response: str = field(default=DeletePackageRequest.request, init=False)

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
