from dataclasses import dataclass
from typing import Optional

from dataclasses_jsonschema import JsonSchemaMixin

from arcor2.data.rpc.common import RPC


class BuildProject(RPC):
    @dataclass
    class Request(RPC.Request):
        """Calls Build service to generate execution package and uploads it to
        the Execution service."""

        @dataclass
        class Args(JsonSchemaMixin):
            project_id: str
            package_name: str

        args: Args

    @dataclass
    class Response(RPC.Response):
        @dataclass
        class Data(JsonSchemaMixin):
            package_id: str

        data: Optional[Data] = None


# ----------------------------------------------------------------------------------------------------------------------


class TemporaryPackage(RPC):
    @dataclass
    class Request(RPC.Request):
        @dataclass
        class Args(JsonSchemaMixin):
            start_paused: bool = False
            breakpoints: Optional[set[str]] = None

        args: Optional[Args] = None

    @dataclass
    class Response(RPC.Response):
        pass
