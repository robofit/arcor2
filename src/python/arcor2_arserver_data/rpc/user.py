from dataclasses import dataclass

from dataclasses_jsonschema import JsonSchemaMixin

from arcor2.data.rpc.common import RPC


class RegisterUser(RPC):
    @dataclass
    class Request(RPC.Request):
        @dataclass
        class Args(JsonSchemaMixin):
            user_name: str

        args: Args

    @dataclass
    class Response(RPC.Response):
        pass
