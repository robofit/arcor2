from dataclasses import dataclass, field
from typing import Optional

from dataclasses_jsonschema import JsonSchemaMixin

from arcor2.data.common import IdDesc, Parameter, Pose, Scene
from arcor2.data.object_type import ObjectModel
from arcor2.data.rpc.common import RPC, IdArgs


@dataclass
class RenameArgs(JsonSchemaMixin):

    id: str
    new_name: str


# ----------------------------------------------------------------------------------------------------------------------


class SceneObjectUsage(RPC):
    @dataclass
    class Request(RPC.Request):
        args: IdArgs = field(metadata=dict(description="ID could be object or service."))

    @dataclass
    class Response(RPC.Response):
        data: Optional[set[str]] = None


# ----------------------------------------------------------------------------------------------------------------------


class AddObjectToScene(RPC):
    @dataclass
    class Request(RPC.Request):
        @dataclass
        class Args(JsonSchemaMixin):
            name: str
            type: str
            pose: Optional[Pose] = None
            parameters: list[Parameter] = field(default_factory=list)

        args: Args
        dry_run: bool = False

    @dataclass
    class Response(RPC.Response):
        pass


# ----------------------------------------------------------------------------------------------------------------------


class UpdateObjectParameters(RPC):
    @dataclass
    class Request(RPC.Request):
        @dataclass
        class Args(JsonSchemaMixin):
            id: str
            parameters: list[Parameter] = field(default_factory=list)

        args: Args
        dry_run: bool = False

    @dataclass
    class Response(RPC.Response):
        pass


# ----------------------------------------------------------------------------------------------------------------------


class RemoveFromScene(RPC):
    @dataclass
    class Request(RPC.Request):
        @dataclass
        class Args(IdArgs):
            force: bool = False

        args: Args
        dry_run: bool = False

    @dataclass
    class Response(RPC.Response):
        pass


# ----------------------------------------------------------------------------------------------------------------------


class SaveScene(RPC):
    @dataclass
    class Request(RPC.Request):

        dry_run: bool = False

    @dataclass
    class Response(RPC.Response):
        pass


# ----------------------------------------------------------------------------------------------------------------------


class OpenScene(RPC):
    @dataclass
    class Request(RPC.Request):

        args: IdArgs

    @dataclass
    class Response(RPC.Response):
        pass


# ----------------------------------------------------------------------------------------------------------------------


class ListScenes(RPC):
    @dataclass
    class Request(RPC.Request):
        pass

    @dataclass
    class Response(RPC.Response):
        @dataclass
        class Data(IdDesc):
            problems: Optional[list[str]] = None

        data: Optional[list[Data]] = None


# ----------------------------------------------------------------------------------------------------------------------


class GetScene(RPC):
    @dataclass
    class Request(RPC.Request):

        args: IdArgs

    @dataclass
    class Response(RPC.Response):

        data: Optional[Scene] = None


# ----------------------------------------------------------------------------------------------------------------------


class NewScene(RPC):
    @dataclass
    class Request(RPC.Request):
        @dataclass
        class Args(JsonSchemaMixin):
            name: str
            description: str = field(default_factory=str)

        args: Args
        dry_run: bool = False

    @dataclass
    class Response(RPC.Response):
        pass


# ----------------------------------------------------------------------------------------------------------------------


class CloseScene(RPC):
    @dataclass
    class Request(RPC.Request):
        @dataclass
        class Args(JsonSchemaMixin):
            force: bool = False

        args: Args = field(default_factory=Args)
        dry_run: bool = False

    @dataclass
    class Response(RPC.Response):
        pass


# ----------------------------------------------------------------------------------------------------------------------


class UpdateObjectPose(RPC):
    @dataclass
    class Request(RPC.Request):
        @dataclass
        class Args(JsonSchemaMixin):
            object_id: str
            pose: Pose

        args: Args
        dry_run: bool = False

    @dataclass
    class Response(RPC.Response):
        pass


# ----------------------------------------------------------------------------------------------------------------------


class RenameObject(RPC):
    @dataclass
    class Request(RPC.Request):

        args: RenameArgs
        dry_run: bool = False

    @dataclass
    class Response(RPC.Response):
        pass


# ----------------------------------------------------------------------------------------------------------------------


class RenameScene(RPC):
    @dataclass
    class Request(RPC.Request):

        args: RenameArgs
        dry_run: bool = False

    @dataclass
    class Response(RPC.Response):
        pass


# ----------------------------------------------------------------------------------------------------------------------


class DeleteScene(RPC):
    @dataclass
    class Request(RPC.Request):

        args: IdArgs
        dry_run: bool = False

    @dataclass
    class Response(RPC.Response):

        data: Optional[set[str]] = None


# ----------------------------------------------------------------------------------------------------------------------


class ProjectsWithScene(RPC):
    @dataclass
    class Request(RPC.Request):

        args: IdArgs

    @dataclass
    class Response(RPC.Response):

        data: Optional[set[str]] = None


# ----------------------------------------------------------------------------------------------------------------------


class UpdateSceneDescription(RPC):
    @dataclass
    class Request(RPC.Request):
        @dataclass
        class Args(JsonSchemaMixin):
            scene_id: str
            new_description: str

        args: Args

    @dataclass
    class Response(RPC.Response):
        pass


# ----------------------------------------------------------------------------------------------------------------------


class CopyScene(RPC):
    @dataclass
    class Request(RPC.Request):
        @dataclass
        class Args(JsonSchemaMixin):
            source_id: str
            target_name: str

        args: Args

    @dataclass
    class Response(RPC.Response):

        data: Optional[str] = None


# ----------------------------------------------------------------------------------------------------------------------


class StartScene(RPC):
    @dataclass
    class Request(RPC.Request):
        dry_run: bool = False

    @dataclass
    class Response(RPC.Response):
        pass


# ----------------------------------------------------------------------------------------------------------------------


class StopScene(RPC):
    @dataclass
    class Request(RPC.Request):
        dry_run: bool = False

    @dataclass
    class Response(RPC.Response):
        pass


# ----------------------------------------------------------------------------------------------------------------------


class AddVirtualCollisionObjectToScene(RPC):
    @dataclass
    class Request(RPC.Request):
        @dataclass
        class Args(JsonSchemaMixin):
            name: str
            pose: Pose
            model: ObjectModel

        args: Args
        dry_run: bool = False

    @dataclass
    class Response(RPC.Response):
        pass
