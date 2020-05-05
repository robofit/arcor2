# -*- coding: utf-8 -*-

from typing import List, Set

from dataclasses import dataclass, field
from dataclasses_jsonschema import JsonSchemaMixin

from arcor2.data.common import IdDesc, SceneService, Pose
from arcor2.data.rpc.common import IdArgs, Request, Response, wo_suffix, TypeArgs


@dataclass
class RenameArgs(JsonSchemaMixin):

    id: str
    new_name: str

# ----------------------------------------------------------------------------------------------------------------------


@dataclass
class SceneObjectUsageRequest(Request):

    args: IdArgs = field(metadata=dict(description="ID could be object or service."))
    request: str = field(default=wo_suffix(__qualname__), init=False)  # type: ignore  # noqa: F821


@dataclass
class SceneObjectUsageResponse(Response):

    data: Set[str] = field(default_factory=set)
    response: str = field(default=SceneObjectUsageRequest.request, init=False)


# ----------------------------------------------------------------------------------------------------------------------


@dataclass
class AutoAddObjectToSceneRequest(Request):

    args: TypeArgs
    dry_run: bool = False
    request: str = field(default=wo_suffix(__qualname__), init=False)  # type: ignore  # noqa: F821


@dataclass
class AutoAddObjectToSceneResponse(Response):

    response: str = field(default=AutoAddObjectToSceneRequest.request, init=False)


# ----------------------------------------------------------------------------------------------------------------------

@dataclass
class AddObjectToSceneRequestArgs(JsonSchemaMixin):

    name: str
    type: str
    pose: Pose


@dataclass
class AddObjectToSceneRequest(Request):

    args: AddObjectToSceneRequestArgs
    dry_run: bool = False
    request: str = field(default=wo_suffix(__qualname__), init=False)  # type: ignore  # noqa: F821


@dataclass
class AddObjectToSceneResponse(Response):

    response: str = field(default=AddObjectToSceneRequest.request, init=False)

# ----------------------------------------------------------------------------------------------------------------------


@dataclass
class AddServiceToSceneRequest(Request):

    args: SceneService
    dry_run: bool = False
    request: str = field(default=wo_suffix(__qualname__), init=False)  # type: ignore  # noqa: F821


@dataclass
class AddServiceToSceneResponse(Response):

    response: str = field(default=AddServiceToSceneRequest.request, init=False)

# ----------------------------------------------------------------------------------------------------------------------


@dataclass
class RemoveFromSceneArgs(IdArgs):

    force: bool = False


@dataclass
class RemoveFromSceneRequest(Request):

    args: RemoveFromSceneArgs
    dry_run: bool = False
    request: str = field(default=wo_suffix(__qualname__), init=False)  # type: ignore  # noqa: F821


@dataclass
class RemoveFromSceneResponse(Response):
    response: str = field(default=RemoveFromSceneRequest.request, init=False)


# ----------------------------------------------------------------------------------------------------------------------


@dataclass
class SaveSceneRequest(Request):

    request: str = field(default=wo_suffix(__qualname__), init=False)  # type: ignore  # noqa: F821


@dataclass
class SaveSceneResponse(Response):

    response: str = field(default=SaveSceneRequest.request, init=False)


# ----------------------------------------------------------------------------------------------------------------------


@dataclass
class OpenSceneRequest(Request):

    args: IdArgs
    request: str = field(default=wo_suffix(__qualname__), init=False)  # type: ignore  # noqa: F821


@dataclass
class OpenSceneResponse(Response):

    response: str = field(default=OpenSceneRequest.request, init=False)


# ----------------------------------------------------------------------------------------------------------------------


@dataclass
class ListScenesRequest(Request):

    request: str = field(default=wo_suffix(__qualname__), init=False)  # type: ignore  # noqa: F821


@dataclass
class ListScenesResponse(Response):

    data: List[IdDesc] = field(default_factory=list)
    response: str = field(default=ListScenesRequest.request, init=False)


# ----------------------------------------------------------------------------------------------------------------------


@dataclass
class NewSceneRequestArgs(JsonSchemaMixin):

    name: str
    desc: str = field(default_factory=str)


@dataclass
class NewSceneRequest(Request):

    args: NewSceneRequestArgs
    dry_run: bool = False
    request: str = field(default=wo_suffix(__qualname__), init=False)  # type: ignore  # noqa: F821


@dataclass
class NewSceneResponse(Response):

    response: str = field(default=NewSceneRequest.request, init=False)

# ----------------------------------------------------------------------------------------------------------------------


@dataclass
class CloseSceneRequestArgs(JsonSchemaMixin):

    force: bool = False


@dataclass
class CloseSceneRequest(Request):

    args: CloseSceneRequestArgs = field(default_factory=CloseSceneRequestArgs)
    dry_run: bool = False
    request: str = field(default=wo_suffix(__qualname__), init=False)  # type: ignore  # noqa: F821


@dataclass
class CloseSceneResponse(Response):

    response: str = field(default=CloseSceneRequest.request, init=False)

# ----------------------------------------------------------------------------------------------------------------------


@dataclass
class UpdateObjectPoseRequestArgs(JsonSchemaMixin):

    object_id: str
    pose: Pose


@dataclass
class UpdateObjectPoseRequest(Request):

    args: UpdateObjectPoseRequestArgs
    request: str = field(default=wo_suffix(__qualname__), init=False)  # type: ignore  # noqa: F821


@dataclass
class UpdateObjectPoseResponse(Response):

    response: str = field(default=UpdateObjectPoseRequest.request, init=False)

# ----------------------------------------------------------------------------------------------------------------------


@dataclass
class RenameObjectRequest(Request):

    args: RenameArgs
    dry_run: bool = False
    request: str = field(default=wo_suffix(__qualname__), init=False)  # type: ignore  # noqa: F821


@dataclass
class RenameObjectResponse(Response):

    response: str = field(default=RenameObjectRequest.request, init=False)


# ----------------------------------------------------------------------------------------------------------------------


@dataclass
class RenameSceneRequest(Request):

    args: RenameArgs
    dry_run: bool = False
    request: str = field(default=wo_suffix(__qualname__), init=False)  # type: ignore  # noqa: F821


@dataclass
class RenameSceneResponse(Response):

    response: str = field(default=RenameSceneRequest.request, init=False)

# ----------------------------------------------------------------------------------------------------------------------


@dataclass
class DeleteSceneRequest(Request):

    args: IdArgs
    dry_run: bool = False
    request: str = field(default=wo_suffix(__qualname__), init=False)  # type: ignore  # noqa: F821


@dataclass
class DeleteSceneResponse(Response):

    data: Set[str] = field(default_factory=set)
    response: str = field(default=DeleteSceneRequest.request, init=False)

# ----------------------------------------------------------------------------------------------------------------------


@dataclass
class ProjectsWithSceneRequest(Request):

    args: IdArgs
    request: str = field(default=wo_suffix(__qualname__), init=False)  # type: ignore  # noqa: F821


@dataclass
class ProjectsWithSceneResponse(Response):

    data: Set[str] = field(default_factory=set)
    response: str = field(default=ProjectsWithSceneRequest.request, init=False)

# ----------------------------------------------------------------------------------------------------------------------


@dataclass
class UpdateSceneDescriptionArgs(JsonSchemaMixin):

    scene_id: str
    new_description: str


@dataclass
class UpdateSceneDescriptionRequest(Request):

    args: UpdateSceneDescriptionArgs
    request: str = field(default=wo_suffix(__qualname__), init=False)  # type: ignore  # noqa: F821


@dataclass
class UpdateSceneDescriptionResponse(Response):

    response: str = field(default=UpdateSceneDescriptionRequest.request, init=False)

# ----------------------------------------------------------------------------------------------------------------------


@dataclass
class UpdateServiceConfigurationArgs(JsonSchemaMixin):

    type: str
    new_configuration: str


@dataclass
class UpdateServiceConfigurationRequest(Request):

    args: UpdateServiceConfigurationArgs
    dry_run: bool = False
    request: str = field(default=wo_suffix(__qualname__), init=False)  # type: ignore  # noqa: F821


@dataclass
class UpdateServiceConfigurationResponse(Response):

    response: str = field(default=UpdateServiceConfigurationRequest.request, init=False)

# ----------------------------------------------------------------------------------------------------------------------


@dataclass
class CopySceneArgs(JsonSchemaMixin):

    source_id: str
    target_name: str


@dataclass
class CopySceneRequest(Request):

    args: CopySceneArgs
    request: str = field(default=wo_suffix(__qualname__), init=False)  # type: ignore  # noqa: F821


@dataclass
class CopySceneResponse(Response):

    data: str = ""
    response: str = field(default=CopySceneRequest.request, init=False)
