# -*- coding: utf-8 -*-

from typing import List, Optional
from datetime import datetime

from dataclasses import dataclass, field
from dataclasses_jsonschema import JsonSchemaMixin

from arcor2.data.common import PackageState, ActionState, CurrentAction
from arcor2.data.execution import PackageMeta
from arcor2.data.rpc.common import IdArgs, Request, Response, wo_suffix


@dataclass
class BuildProjectArgs(JsonSchemaMixin):

    project_id: str
    package_name: str


@dataclass
class BuildProjectRequest(Request):
    """
    Calls Build service to generate execution package and uploads it to the Execution service.
    """

    args: BuildProjectArgs
    request: str = field(default=wo_suffix(__qualname__), init=False)  # type: ignore  # noqa: F821


@dataclass
class BuildProjectData(JsonSchemaMixin):

    package_id: str


@dataclass
class BuildProjectResponse(Response):

    data: Optional[BuildProjectData] = None
    response: str = field(default=BuildProjectRequest.request, init=False)

# ----------------------------------------------------------------------------------------------------------------------


@dataclass
class UploadPackageArgs(JsonSchemaMixin):

    id: str = field(metadata=dict(description="Id of the execution package."))
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
    project_id: str
    modified: datetime = field(metadata=dict(
        description="Last modification of the project embedded in the execution package."))
    # modified_files: List[ModifiedFile] = field(default_factory=list)
    package_meta: PackageMeta = field(metadata=dict(description="Content of 'package.json'."))


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
class RenamePackageArgs(JsonSchemaMixin):

    package_id: str
    new_name: str


@dataclass
class RenamePackageRequest(Request):

    args: RenamePackageArgs
    request: str = field(default=wo_suffix(__qualname__), init=False)  # type: ignore  # noqa: F821


@dataclass
class RenamePackageResponse(Response):

    response: str = field(default=RenamePackageRequest.request, init=False)

# ----------------------------------------------------------------------------------------------------------------------


@dataclass
class RunPackageRequest(Request):

    args: IdArgs
    request: str = field(default=wo_suffix(__qualname__), init=False)  # type: ignore  # noqa: F821


@dataclass
class RunPackageResponse(Response):

    response: str = field(default=RunPackageRequest.request, init=False)


# ----------------------------------------------------------------------------------------------------------------------


@dataclass
class StopPackageRequest(Request):

    request: str = field(default=wo_suffix(__qualname__), init=False)  # type: ignore  # noqa: F821


@dataclass
class StopPackageResponse(Response):

    response: str = field(default=StopPackageRequest.request, init=False)


# ----------------------------------------------------------------------------------------------------------------------


@dataclass
class PausePackageRequest(Request):

    request: str = field(default=wo_suffix(__qualname__), init=False)  # type: ignore  # noqa: F821


@dataclass
class PausePackageResponse(Response):

    response: str = field(default=PausePackageRequest.request, init=False)


# ----------------------------------------------------------------------------------------------------------------------

@dataclass
class PackageStateRequest(Request):

    request: str = field(default=wo_suffix(__qualname__), init=False)  # type: ignore  # noqa: F821


@dataclass
class PackageStateData(JsonSchemaMixin):

    project: PackageState = field(default_factory=PackageState)
    action: Optional[ActionState] = None
    action_args: Optional[CurrentAction] = None


@dataclass
class PackageStateResponse(Response):

    data: PackageStateData = field(default_factory=PackageStateData)
    response: str = field(default=PackageStateRequest.request, init=False)


# ----------------------------------------------------------------------------------------------------------------------


@dataclass
class ResumePackageRequest(Request):

    request: str = field(default=wo_suffix(__qualname__), init=False)  # type: ignore  # noqa: F821


@dataclass
class ResumePackageResponse(Response):

    response: str = field(default=ResumePackageRequest.request, init=False)
