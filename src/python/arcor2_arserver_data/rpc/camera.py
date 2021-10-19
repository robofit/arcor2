from dataclasses import dataclass, field
from typing import Optional

from dataclasses_jsonschema import JsonSchemaMixin

from arcor2.data.camera import CameraParameters
from arcor2.data.rpc.common import RPC


class CameraColorImage(RPC):
    @dataclass
    class Request(RPC.Request):
        @dataclass
        class Args(JsonSchemaMixin):
            id: str = field(metadata=dict(description="Camera id."))

        args: Args

    @dataclass
    class Response(RPC.Response):

        data: Optional[str] = field(default=None, repr=False)


class CameraColorParameters(RPC):
    @dataclass
    class Request(RPC.Request):
        @dataclass
        class Args(JsonSchemaMixin):
            id: str = field(metadata=dict(description="Camera id."))

        args: Args

    @dataclass
    class Response(RPC.Response):

        data: Optional[CameraParameters] = None


class CalibrateCamera(RPC):
    @dataclass
    class Request(RPC.Request):
        @dataclass
        class Args(JsonSchemaMixin):
            id: str = field(metadata=dict(description="Camera id."))

        args: Args

    @dataclass
    class Response(RPC.Response):
        pass
