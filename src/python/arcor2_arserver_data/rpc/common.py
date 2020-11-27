from dataclasses import dataclass, field
from typing import Optional, Set

from dataclasses_jsonschema import JsonSchemaMixin

from arcor2.data.camera import CameraParameters
from arcor2.data.common import Pose
from arcor2.data.rpc.common import RPC

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
            supported_parameter_types: Set[str] = field(default_factory=set)
            supported_rpc_requests: Set[str] = field(default_factory=set)

        data: Optional[Data] = None


# ----------------------------------------------------------------------------------------------------------------------


class Calibration(RPC):
    @dataclass
    class Request(RPC.Request):
        @dataclass
        class Args(JsonSchemaMixin):
            camera_parameters: CameraParameters
            image: str = field(metadata=dict(description="Base64 encoded image."))

        args: Args

    @dataclass
    class Response(RPC.Response):

        data: Optional[Pose] = None
