from dataclasses import dataclass, field
from typing import List, Optional, Set

from dataclasses_jsonschema import JsonSchemaMixin

from arcor2.data.common import IdValue, Parameter, StrEnum
from arcor2.data.object_type import MeshList
from arcor2.data.rpc.common import RPC, IdArgs, RobotArg, TypeArgs
from arcor2_arserver_data.objects import ObjectActions, ObjectTypeMeta


class ActionParamValues(RPC):
    @dataclass
    class Request(RPC.Request):
        @dataclass
        class Args(JsonSchemaMixin):
            id: str = field(metadata=dict(description="Object or service id."))
            param_id: str
            parent_params: List[IdValue] = field(default_factory=list)

        args: Args

    @dataclass
    class Response(RPC.Response):

        data: Optional[Set[str]] = None  # TODO what about other (possible) types than 'str'?


# ----------------------------------------------------------------------------------------------------------------------


class GetObjectTypes(RPC):
    @dataclass
    class Request(RPC.Request):
        pass

    @dataclass
    class Response(RPC.Response):
        data: Optional[List[ObjectTypeMeta]] = None


# ----------------------------------------------------------------------------------------------------------------------


class DeleteObjectType(RPC):
    @dataclass
    class Request(RPC.Request):

        args: IdArgs
        dry_run: bool = False

    @dataclass
    class Response(RPC.Response):
        pass


# ----------------------------------------------------------------------------------------------------------------------


class GetActions(RPC):
    @dataclass
    class Request(RPC.Request):

        args: TypeArgs

    @dataclass
    class Response(RPC.Response):

        data: Optional[ObjectActions] = None


# ----------------------------------------------------------------------------------------------------------------------


class NewObjectType(RPC):
    @dataclass
    class Request(RPC.Request):

        args: ObjectTypeMeta
        dry_run: bool = False

    @dataclass
    class Response(RPC.Response):
        pass


# ----------------------------------------------------------------------------------------------------------------------


class FocusObjectStart(RPC):
    @dataclass
    class Request(RPC.Request):
        @dataclass
        class Args(JsonSchemaMixin):
            object_id: str
            robot: RobotArg

        args: Args

    @dataclass
    class Response(RPC.Response):
        pass


# ----------------------------------------------------------------------------------------------------------------------


class FocusObject(RPC):
    @dataclass
    class Request(RPC.Request):
        @dataclass
        class Args(JsonSchemaMixin):
            object_id: str
            point_idx: int

        args: Args

    @dataclass
    class Response(RPC.Response):
        @dataclass
        class Data(JsonSchemaMixin):
            finished_indexes: List[int]

        data: Optional[Data] = None


# ----------------------------------------------------------------------------------------------------------------------


class FocusObjectDone(RPC):
    @dataclass
    class Request(RPC.Request):
        args: IdArgs

    @dataclass
    class Response(RPC.Response):
        data: Optional[FocusObject.Response.Data] = None


# ----------------------------------------------------------------------------------------------------------------------


class UpdateObjectPoseUsingRobot(RPC):
    @dataclass
    class Request(RPC.Request):
        @dataclass
        class Args(IdArgs):
            class PivotEnum(StrEnum):
                TOP: str = "top"
                MIDDLE: str = "middle"
                BOTTOM: str = "bottom"

            robot: RobotArg
            pivot: PivotEnum = PivotEnum.MIDDLE

        args: Args

    @dataclass
    class Response(RPC.Response):
        pass


# ----------------------------------------------------------------------------------------------------------------------


class ListMeshes(RPC):
    @dataclass
    class Request(RPC.Request):
        pass

    @dataclass
    class Response(RPC.Response):
        data: Optional[MeshList] = None


# ----------------------------------------------------------------------------------------------------------------------


class AddOverride(RPC):
    @dataclass
    class Request(RPC.Request):
        @dataclass
        class Args(JsonSchemaMixin):
            id: str
            override: Parameter

        args: Args
        dry_run: bool = False

    @dataclass
    class Response(RPC.Response):
        pass


# ----------------------------------------------------------------------------------------------------------------------


class UpdateOverride(RPC):
    @dataclass
    class Request(RPC.Request):
        @dataclass
        class Args(JsonSchemaMixin):
            id: str
            override: Parameter

        args: Args
        dry_run: bool = False

    @dataclass
    class Response(RPC.Response):
        pass


# ----------------------------------------------------------------------------------------------------------------------


class DeleteOverride(RPC):
    @dataclass
    class Request(RPC.Request):
        @dataclass
        class Args(JsonSchemaMixin):
            id: str
            override: Parameter

        args: Args
        dry_run: bool = False

    @dataclass
    class Response(RPC.Response):
        pass
