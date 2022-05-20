from dataclasses import dataclass, field
from typing import Optional

from dataclasses_jsonschema import JsonSchemaMixin

from arcor2.data.camera import CameraParameters
from arcor2.data.rpc.common import RPC
from arcor2_calibration_data import EstimatedPose, MarkerCorners

# ----------------------------------------------------------------------------------------------------------------------


class SystemInfo(RPC):
    @dataclass
    class Request(RPC.Request):
        pass

    @dataclass
    class Response(RPC.Response):
        @dataclass
        class Data(JsonSchemaMixin):
            version: str
            api_version: str
            supported_parameter_types: set[str] = field(default_factory=set)
            supported_rpc_requests: set[str] = field(default_factory=set)

        data: Optional[Data] = None


# ----------------------------------------------------------------------------------------------------------------------


class GetCameraPose(RPC):
    @dataclass
    class Request(RPC.Request):
        @dataclass
        class Args(JsonSchemaMixin):
            camera_parameters: CameraParameters
            image: str = field(metadata=dict(description="Base64 encoded image."), repr=False)
            inverse: bool = False

        args: Args

    @dataclass
    class Response(RPC.Response):

        data: Optional[EstimatedPose] = None


# ----------------------------------------------------------------------------------------------------------------------


class MarkersCorners(RPC):
    @dataclass
    class Request(RPC.Request):
        @dataclass
        class Args(JsonSchemaMixin):
            camera_parameters: CameraParameters
            image: str = field(metadata=dict(description="Base64 encoded image."), repr=False)

        args: Args

    @dataclass
    class Response(RPC.Response):

        data: Optional[list[MarkerCorners]] = None
