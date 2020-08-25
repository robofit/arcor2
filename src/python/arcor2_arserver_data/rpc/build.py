from dataclasses import dataclass, field
from typing import Optional

from dataclasses_jsonschema import JsonSchemaMixin

from arcor2.data.rpc.common import Request, Response, wo_suffix


@dataclass
class BuildProjectArgs(JsonSchemaMixin):

    project_id: str
    package_name: str


@dataclass
class BuildProjectRequest(Request):
    """Calls Build service to generate execution package and uploads it to the
    Execution service."""

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
class TemporaryPackageRequest(Request):

    request: str = field(default=wo_suffix(__qualname__), init=False)  # type: ignore  # noqa: F821


@dataclass
class TemporaryPackageResponse(Response):

    response: str = field(default=TemporaryPackageRequest.request, init=False)
