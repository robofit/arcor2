import os
from typing import Set

from arcor2 import rest
from arcor2.data.common import Pose
from arcor2.data.object_type import MeshFocusAction, Model3dType, Models
from arcor2.exceptions import Arcor2Exception

URL = os.getenv("ARCOR2_SCENE_SERVICE_URL", "http://0.0.0.0:5013")


class SceneServiceException(Arcor2Exception):
    pass


def upsert_collision(model: Models, pose: Pose) -> None:
    """
    Adds arbitrary collision model to the collision scene.
    :param model: Box, Sphere, Cylinder, Mesh
    :param pose: Pose of the collision object.
    :return:

    Example usage:

    >>> from arcor2.data.object_type import Box
    >>> from arcor2.data.common import Pose, Position, Orientation
    >>> box = Box("UniqueBoxId", 0.1, 0.1, 0.1)
    >>> scene_service.upsert_collision(box, Pose(Position(1, 0, 0), Orientation(0, 0, 0, 1)))

    """

    model_id = model.id
    params = model.to_dict()
    del params["id"]
    params[model.__class__.__name__.lower() + "Id"] = model_id

    # TODO temporary hack
    if model.type() == Model3dType.MESH:
        params["mesh_scale_x"] = 1.0
        params["mesh_scale_y"] = 1.0
        params["mesh_scale_z"] = 1.0
        params["transform_id"] = "world"

    rest.put(f"{URL}/collisions/{model.type().value.lower()}", pose, params)


@rest.handle_exceptions(SceneServiceException)
def delete_collision_id(collision_id: str) -> None:
    rest.delete(f"{URL}/collisions/{collision_id}")


@rest.handle_exceptions(SceneServiceException)
def collision_ids() -> Set[str]:
    return set(rest.get_list_primitive(f"{URL}/collisions", str))


@rest.handle_exceptions(SceneServiceException)
def focus(mfa: MeshFocusAction) -> Pose:
    return rest.put(f"{URL}/utils/focus", mfa, data_cls=Pose)


def delete_all_collisions() -> None:

    for cid in collision_ids():
        delete_collision_id(cid)


__ALL__ = [
    SceneServiceException.__name__,
    upsert_collision.__name__,
    delete_collision_id.__name__,
    collision_ids.__name__,
    focus.__name__,
    delete_all_collisions.__name__
]
