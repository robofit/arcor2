from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from dataclasses_jsonschema import JsonSchemaMixin

from arcor2.data.rpc.common import RPC, IdArgs
from arcor2_execution_data.common import PackageSummary


class UploadPackage(RPC):
    @dataclass
    class Request(RPC.Request):
        @dataclass
        class Args(JsonSchemaMixin):
            id: str = field(metadata=dict(description="Id of the execution package."))
            data: str = field(metadata=dict(description="Base64 encoded content of the zip file."), repr=False)

        args: Args

    @dataclass
    class Response(RPC.Response):
        pass


# ----------------------------------------------------------------------------------------------------------------------


class ListPackages(RPC):
    @dataclass
    class Request(RPC.Request):
        pass

    @dataclass
    class ModifiedFile(JsonSchemaMixin):

        filename: str
        modified: datetime

    @dataclass
    class Response(RPC.Response):
        data: list[PackageSummary] = field(default_factory=list)


# ----------------------------------------------------------------------------------------------------------------------


class DeletePackage(RPC):
    @dataclass
    class Request(RPC.Request):
        args: IdArgs

    @dataclass
    class Response(RPC.Response):
        pass


# ----------------------------------------------------------------------------------------------------------------------


class RenamePackage(RPC):
    @dataclass
    class Request(RPC.Request):
        @dataclass
        class Args(JsonSchemaMixin):
            package_id: str
            new_name: str

        args: Args

    @dataclass
    class Response(RPC.Response):
        pass


# ----------------------------------------------------------------------------------------------------------------------


class RunPackage(RPC):
    @dataclass
    class Request(RPC.Request):
        @dataclass
        class Args(IdArgs):
            start_paused: bool = False
            breakpoints: Optional[set[str]] = None

        args: Args

    @dataclass
    class Response(RPC.Response):
        pass


# ----------------------------------------------------------------------------------------------------------------------


class StopPackage(RPC):
    @dataclass
    class Request(RPC.Request):
        pass

    @dataclass
    class Response(RPC.Response):
        pass


# ----------------------------------------------------------------------------------------------------------------------


class PausePackage(RPC):
    @dataclass
    class Request(RPC.Request):
        pass

    @dataclass
    class Response(RPC.Response):
        pass


# ----------------------------------------------------------------------------------------------------------------------


class ResumePackage(RPC):
    @dataclass
    class Request(RPC.Request):
        pass

    @dataclass
    class Response(RPC.Response):
        pass


# ----------------------------------------------------------------------------------------------------------------------


class StepAction(RPC):
    @dataclass
    class Request(RPC.Request):
        pass

    @dataclass
    class Response(RPC.Response):
        pass
