from dataclasses import dataclass, field
from typing import Optional

from dataclasses_jsonschema import JsonSchemaMixin

from arcor2.data.common import IdValue, Parameter, StrEnum
from arcor2.data.object_type import MeshList, ObjectModel
from arcor2.data.rpc.common import RPC, IdArgs, RobotArg, TypeArgs
from arcor2_arserver_data.objects import ObjectActions, ObjectTypeMeta


class ActionParamValues(RPC):
    @dataclass
    class Request(RPC.Request):
        @dataclass
        class Args(JsonSchemaMixin):
            id: str = field(metadata=dict(description="Object or service id."))
            param_id: str
            parent_params: list[IdValue] = field(default_factory=list)

        args: Args

    @dataclass
    class Response(RPC.Response):

        data: Optional[set[str]] = None  # TODO what about other (possible) types than 'str'?


# ----------------------------------------------------------------------------------------------------------------------


class GetObjectTypes(RPC):
    @dataclass
    class Request(RPC.Request):
        pass

    @dataclass
    class Response(RPC.Response):
        data: Optional[list[ObjectTypeMeta]] = None


# ----------------------------------------------------------------------------------------------------------------------


class DeleteObjectTypes(RPC):
    @dataclass
    class Request(RPC.Request):

        args: Optional[set[str]] = None  # None means all of them
        dry_run: bool = False

    @dataclass
    class Response(RPC.Response):
        @dataclass
        class Data(JsonSchemaMixin):
            id: str
            error: str

        data: Optional[list[Data]] = None  # list of types that can't be deleted


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


class UpdateObjectModel(RPC):
    @dataclass
    class Request(RPC.Request):
        @dataclass
        class Args(JsonSchemaMixin):
            object_type_id: str = field(metadata=dict(description="Object or service id."))
            object_model: ObjectModel  # can't use Models (Union) because of C# generator

        args: Args
        dry_run: bool = False

    @dataclass
    class Response(RPC.Response):
        pass


# ----------------------------------------------------------------------------------------------------------------------


class ObjectAimingStart(RPC):
    @dataclass
    class Request(RPC.Request):
        @dataclass
        class Args(JsonSchemaMixin):
            object_id: str
            robot: RobotArg

        args: Args
        dry_run: bool = False

    @dataclass
    class Response(RPC.Response):
        pass


# ----------------------------------------------------------------------------------------------------------------------


class ObjectAimingCancel(RPC):
    @dataclass
    class Request(RPC.Request):
        dry_run: bool = False

    @dataclass
    class Response(RPC.Response):
        pass


# ----------------------------------------------------------------------------------------------------------------------


class ObjectAimingAddPoint(RPC):
    @dataclass
    class Request(RPC.Request):
        @dataclass
        class Args(JsonSchemaMixin):
            point_idx: int

        args: Args
        dry_run: bool = False

    @dataclass
    class Response(RPC.Response):
        @dataclass
        class Data(JsonSchemaMixin):
            finished_indexes: list[int]

        data: Optional[Data] = None


# ----------------------------------------------------------------------------------------------------------------------


class ObjectAimingDone(RPC):
    @dataclass
    class Request(RPC.Request):
        dry_run: bool = False

    @dataclass
    class Response(RPC.Response):
        data: Optional[ObjectAimingAddPoint.Response.Data] = None


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


# ----------------------------------------------------------------------------------------------------------------------


class ObjectTypeUsage(RPC):
    """Returns list of scenes (IDs), where the OT is used."""

    @dataclass
    class Request(RPC.Request):
        args: IdArgs

    @dataclass
    class Response(RPC.Response):
        data: Optional[set[str]] = None
