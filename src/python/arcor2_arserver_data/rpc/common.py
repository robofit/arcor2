from dataclasses import dataclass, field
from typing import Set

from arcor2_calibration_data import CameraParameters
from dataclasses_jsonschema import JsonSchemaMixin

from arcor2.data.common import Pose
from arcor2.data.rpc.common import Request, Response, wo_suffix

# ----------------------------------------------------------------------------------------------------------------------


@dataclass
class SystemInfoRequest(Request):

    request: str = field(default=wo_suffix(__qualname__), init=False)  # type: ignore  # noqa: F821


@dataclass
class SystemInfoData(JsonSchemaMixin):

    version: str = ""
    api_version: str = ""
    supported_parameter_types: Set[str] = field(default_factory=set)
    supported_rpc_requests: Set[str] = field(default_factory=set)


@dataclass
class SystemInfoResponse(Response):

    data: SystemInfoData = field(default_factory=SystemInfoData)
    response: str = field(default=SystemInfoRequest.request, init=False)


# ----------------------------------------------------------------------------------------------------------------------


@dataclass
class CalibrationRequestArgs(JsonSchemaMixin):

    camera_parameters: CameraParameters
    image: str = field(metadata=dict(description="Base64 encoded image."))


@dataclass
class CalibrationRequest(Request):

    args: CalibrationRequestArgs
    request: str = field(default=wo_suffix(__qualname__), init=False)  # type: ignore  # noqa: F821


@dataclass
class CalibrationResponse(Response):

    data: Pose = field(default_factory=Pose)
    response: str = field(default=CalibrationRequest.request, init=False)
