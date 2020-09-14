from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional

from dataclasses_jsonschema import JsonSchemaMixin

from arcor2.data import events
from arcor2.data.rpc.common import RPC, IdArgs
from arcor2_execution_data.common import PackageSummary


class UploadPackage(RPC):
    @dataclass
    class Request(RPC.Request):
        @dataclass
        class Args(JsonSchemaMixin):
            id: str = field(metadata=dict(description="Id of the execution package."))
            data: str = field(metadata=dict(description="Base64 encoded content of the zip file."))

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
        data: List[PackageSummary] = field(default_factory=list)


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
            cleanup_after_run: bool = True

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


class PackageState(RPC):
    @dataclass
    class Request(RPC.Request):
        pass

    @dataclass
    class Response(RPC.Response):
        @dataclass
        class Data(JsonSchemaMixin):
            project: events.PackageState.Data
            action: Optional[events.ActionState.Data] = None
            action_args: Optional[events.CurrentAction.Data] = None

        data: Optional[Data] = None


# ----------------------------------------------------------------------------------------------------------------------


class ResumePackage(RPC):
    @dataclass
    class Request(RPC.Request):
        pass

    @dataclass
    class Response(RPC.Response):
        pass
