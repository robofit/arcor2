import os
from dataclasses import dataclass
from typing import Optional, Set

from dataclasses_jsonschema import JsonSchemaMixin

from arcor2 import rest
from arcor2.data.common import Pose
from arcor2.data.object_type import MeshFocusAction, Model3dType, Models
from arcor2.exceptions import Arcor2Exception

URL = os.getenv("ARCOR2_SCENE_SERVICE_URL", "http://0.0.0.0:5013")


class SceneServiceException(Arcor2Exception):
    pass


@dataclass
class MeshParameters(JsonSchemaMixin):

    mesh_scale_x: float = 1.0
    mesh_scale_y: float = 1.0
    mesh_scale_z: float = 1.0
    transform_id: str = "world"


def upsert_collision(model: Models, pose: Pose, mesh_parameters: Optional[MeshParameters] = None) -> None:
    """
    Adds arbitrary collision model to the collision scene.
    :param model: Box, Sphere, Cylinder, Mesh
    :param pose: Pose of the collision object.
    :param mesh_parameters: Some additional parameters might be specified for mesh collision model.
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

    if model.type() == Model3dType.MESH and mesh_parameters:
        params.update(mesh_parameters.to_dict())

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


__all__ = [
    SceneServiceException.__name__,
    upsert_collision.__name__,
    delete_collision_id.__name__,
    collision_ids.__name__,
    focus.__name__,
    delete_all_collisions.__name__
]
