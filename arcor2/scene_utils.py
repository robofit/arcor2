from arcor2.data.common import Scene, SceneObject
from arcor2.exceptions import SceneObjectNotFound


def get_scene_object(scene: Scene, obj_id: str) -> SceneObject:  # TODO cache it somehow?

    for obj in scene.objects:
        if obj.id == obj_id:
            return obj

    raise SceneObjectNotFound
