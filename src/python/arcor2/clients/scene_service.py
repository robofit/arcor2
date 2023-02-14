import os
import time
from dataclasses import dataclass

from dataclasses_jsonschema import JsonSchemaMixin

from arcor2 import rest
from arcor2.data.common import Pose
from arcor2.data.object_type import Model3dType, Models
from arcor2.data.scene import LineCheck, LineCheckResult, MeshFocusAction
from arcor2.exceptions import Arcor2Exception
from arcor2.exceptions.helpers import handle
from arcor2.logging import get_logger

URL = os.getenv("ARCOR2_SCENE_SERVICE_URL", "http://0.0.0.0:5013")


logger = get_logger("Scene")


class SceneServiceException(Arcor2Exception):
    pass


@dataclass
class MeshParameters(JsonSchemaMixin):

    mesh_scale_x: float = 1.0
    mesh_scale_y: float = 1.0
    mesh_scale_z: float = 1.0
    transform_id: str = "world"


def wait_for(timeout: float = 10.0) -> None:

    start_time = time.monotonic()
    while time.monotonic() < start_time + timeout:
        try:
            started()
            return
        except SceneServiceException:
            time.sleep(1.0)

    raise SceneServiceException("Failed to contact Scene service.")


@handle(SceneServiceException, logger, message="Failed to add or update the collision model.")
def upsert_collision(model: Models, pose: Pose, mesh_parameters: None | MeshParameters = None) -> None:
    """Adds arbitrary collision model to the collision scene.

    :param model: Box, Sphere, Cylinder, Mesh
    :param pose: Pose of the collision object.
    :param mesh_parameters: Some additional parameters might be specified for mesh collision model.
    :return:

    Example usage:

    >>> from arcor2.clients import scene_service
    >>> from arcor2.data.object_type import Box
    >>> from arcor2.data.common import Pose, Position, Orientation
    >>> box = Box("UniqueBoxId", 0.1, 0.1, 0.1)
    >>> scene_service.upsert_collision(box, Pose(Position(1, 0, 0), Orientation(0, 0, 0, 1)))
    """

    params = model.to_dict()
    model_type = model.type().value.lower()

    params[f"{model_type}Id"] = model.id
    del params["id"]

    if model.type() == Model3dType.MESH:

        params["meshFileId"] = params.pop("asset_id")

        if mesh_parameters:
            params.update(mesh_parameters.to_dict())

    rest.call(rest.Method.PUT, f"{URL}/collisions/{model_type}", body=pose, params=params)


@handle(SceneServiceException, logger, message="Failed to delete the collision.")
def delete_collision_id(collision_id: str) -> None:
    rest.call(rest.Method.DELETE, f"{URL}/collisions/{collision_id}")


@handle(SceneServiceException, logger, message="Failed to list collisions.")
def collision_ids() -> set[str]:
    return set(rest.call(rest.Method.GET, f"{URL}/collisions", list_return_type=str))


@handle(SceneServiceException, logger, message="Failed to focus the object.")
def focus(mfa: MeshFocusAction) -> Pose:
    return rest.call(rest.Method.PUT, f"{URL}/utils/focus", body=mfa, return_type=Pose)


@handle(SceneServiceException, logger, message="Failed to check whether line is safe.")
def line_check(lc: LineCheck) -> LineCheckResult:
    """This is specific to arcor2 Scene service.

    :param lc:
    :return:
    """
    return rest.call(rest.Method.PUT, f"{URL}/utils/line-safe", body=lc, return_type=LineCheckResult)


def delete_all_collisions() -> None:

    for cid in collision_ids():
        delete_collision_id(cid)


@handle(SceneServiceException, logger, message="Failed to start the scene.")
def start(timeout: rest.OptTimeout = None) -> None:
    """To be called after all objects are created."""

    rest.call(rest.Method.PUT, f"{URL}/system/start", timeout=timeout)


@handle(SceneServiceException, logger, message="Failed to stop the scene.")
def stop() -> None:
    """To be called when project is closed or when main script ends."""

    rest.call(rest.Method.PUT, f"{URL}/system/stop")


@handle(SceneServiceException, logger, message="Failed to get scene state.")
def started() -> bool:
    """Checks whether the scene is running."""

    return rest.call(rest.Method.GET, f"{URL}/system/running", return_type=bool)


@handle(SceneServiceException, logger, message="Failed to get transforms.")
def transforms() -> set[str]:
    """Gets available transformations."""

    return set(rest.call(rest.Method.GET, f"{URL}/transforms", list_return_type=str))


@handle(SceneServiceException, logger, message="Failed to add or update the transform.")
def upsert_transform(transform_id: str, parent: str, pose: Pose) -> None:
    """Add or updates transform."""

    rest.call(rest.Method.PUT, f"{URL}/transforms", body=pose, params={"transformId": transform_id, "parent": parent})


@handle(SceneServiceException, logger, message="Failed to get the local pose.")
def local_pose(transform_id: str) -> Pose:
    """Gets relative pose to parent."""

    return rest.call(rest.Method.GET, f"{URL}/transforms/{transform_id}/pose/local", return_type=Pose)


@handle(SceneServiceException, logger, message="Failed to get the world pose.")
def world_pose(transform_id: str) -> Pose:
    """Gets absolute pose in world space."""

    return rest.call(rest.Method.GET, f"{URL}/transforms/{transform_id}/pose/world", return_type=Pose)


__all__ = [
    SceneServiceException.__name__,
    upsert_collision.__name__,
    delete_collision_id.__name__,
    collision_ids.__name__,
    focus.__name__,
    delete_all_collisions.__name__,
    start.__name__,
    stop.__name__,
    transforms.__name__,
    upsert_transform.__name__,
    local_pose.__name__,
    world_pose.__name__,
]
