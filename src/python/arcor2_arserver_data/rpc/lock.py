from dataclasses import dataclass

from dataclasses_jsonschema import JsonSchemaMixin

from arcor2.data.common import StrEnum
from arcor2.data.rpc.common import RPC


class UpdateType(StrEnum):
    TREE: str = "TREE"
    OBJECT: str = "OBJECT"


# ----------------------------------------------------------------------------------------------------------------------


class ReadLock(RPC):
    @dataclass
    class Request(RPC.Request):
        @dataclass
        class Args(JsonSchemaMixin):
            object_id: str

        args: Args

    @dataclass
    class Response(RPC.Response):
        pass


# ----------------------------------------------------------------------------------------------------------------------


class WriteLock(RPC):
    @dataclass
    class Request(RPC.Request):
        @dataclass
        class Args(JsonSchemaMixin):
            object_id: str
            lock_tree: bool = False

        args: Args

    @dataclass
    class Response(RPC.Response):
        pass


# ----------------------------------------------------------------------------------------------------------------------


class ReadUnlock(RPC):
    @dataclass
    class Request(RPC.Request):
        @dataclass
        class Args(JsonSchemaMixin):
            object_id: str

        args: Args

    @dataclass
    class Response(RPC.Response):
        pass


# ----------------------------------------------------------------------------------------------------------------------


class WriteUnlock(RPC):
    @dataclass
    class Request(RPC.Request):
        @dataclass
        class Args(JsonSchemaMixin):
            object_id: str

        args: Args

    @dataclass
    class Response(RPC.Response):
        pass


# ----------------------------------------------------------------------------------------------------------------------


class UpdateLock(RPC):
    @dataclass
    class Request(RPC.Request):
        @dataclass
        class Args(JsonSchemaMixin):
            object_id: str
            new_type: UpdateType

        args: Args

    @dataclass
    class Response(RPC.Response):
        pass
