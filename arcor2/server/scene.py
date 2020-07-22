import asyncio
from typing import AsyncIterator, Optional, Set

from arcor2 import helpers as hlp
from arcor2.cached import CachedScene, UpdateableCachedScene
from arcor2.clients import aio_persistent_storage as storage, aio_scene_service as scene_srv
from arcor2.data.common import Pose, SceneObject
from arcor2.data.object_type import Models
from arcor2.exceptions import Arcor2Exception
from arcor2.object_types.abstract import Generic, GenericWithPose
from arcor2.server import globals as glob


def instances_names() -> Set[str]:
    return {obj.name for obj in glob.SCENE_OBJECT_INSTANCES.values()}


async def scenes() -> AsyncIterator[CachedScene]:

    for scene_id in (await storage.get_scenes()).items:
        yield CachedScene(await storage.get_scene(scene_id.id))


async def scene_names() -> Set[str]:
    return {scene.name for scene in (await storage.get_scenes()).items}


async def set_object_pose(obj: GenericWithPose, pose: Pose) -> None:
    """
    Object pose is property that might call scene service - that's why it should be called using executor.
    :param obj:
    :param pose:
    :return:
    """

    await hlp.run_in_executor(setattr, obj, "pose", pose)


async def add_object_to_scene(obj: SceneObject, add_to_scene: bool = True,
                              dry_run: bool = False, parent_id: Optional[str] = None) -> None:
    """

    :param obj:
    :param add_to_scene: Set to false to only create object instance and add its collision model (if any).
    :return:
    """

    assert glob.SCENE
    assert not obj.children

    if obj.type not in glob.OBJECT_TYPES:
        raise Arcor2Exception("Unknown object type.")

    obj_type = glob.OBJECT_TYPES[obj.type]

    if obj_type.meta.disabled:
        raise Arcor2Exception("Object type disabled.")

    # TODO check whether object has all required settings

    # TODO check whether object needs parent and if so, if the parent is in scene and parent_id is set
    if obj_type.meta.needs_parent_type:
        pass

    if obj_type.meta.has_pose and obj.pose is None:
        raise Arcor2Exception("Object requires pose.")

    if not obj_type.meta.has_pose and obj.pose is not None:
        raise Arcor2Exception("Object do not have pose.")

    if obj_type.meta.abstract:
        raise Arcor2Exception("Cannot instantiate abstract type.")

    if obj.id in glob.SCENE_OBJECT_INSTANCES:
        raise Arcor2Exception("Object/service with that id already exists.")

    if obj.name in instances_names():
        raise Arcor2Exception("Name is already used.")

    if not hlp.is_valid_identifier(obj.name):
        raise Arcor2Exception("Object name invalid (should be snake_case).")

    if dry_run:
        return None

    await glob.logger.debug(f"Creating instance {obj.id} ({obj.type}).")

    # TODO settings -> dataclass

    assert obj_type.type_def is not None

    if issubclass(obj_type.type_def, GenericWithPose):
        assert obj.pose is not None
        coll_model: Optional[Models] = None
        if obj_type.meta.object_model:
            coll_model = obj_type.meta.object_model.model()

        # TODO RPC should return here (instantiation could take long time) -> events
        glob.SCENE_OBJECT_INSTANCES[obj.id] = await hlp.run_in_executor(
            obj_type.type_def, obj.id, obj.name, obj.pose, coll_model)

    elif issubclass(obj_type.type_def, Generic):
        assert obj.pose is None
        # TODO RPC should return here (instantiation could take long time) -> events
        glob.SCENE_OBJECT_INSTANCES[obj.id] = await hlp.run_in_executor(obj_type.type_def, obj.id, obj.name)

    else:
        raise Arcor2Exception("Object type with unknown base.")

    if add_to_scene:
        glob.SCENE.upsert_object(obj)

    return None


async def clear_scene(do_cleanup: bool = True) -> None:

    await glob.logger.info("Clearing the scene.")
    glob.SCENE_OBJECT_INSTANCES.clear()
    await asyncio.gather(*[hlp.run_in_executor(obj.cleanup) for obj in glob.SCENE_OBJECT_INSTANCES.values()])
    glob.SCENE = None


async def open_scene(scene_id: str) -> None:

    asyncio.ensure_future(scene_srv.delete_all_collisions())  # just for sure
    glob.SCENE = UpdateableCachedScene(await storage.get_scene(scene_id))

    try:
        await asyncio.gather(*[add_object_to_scene(obj, add_to_scene=False) for obj in glob.SCENE.objects])
    except Arcor2Exception as e:
        await clear_scene()
        raise Arcor2Exception(f"Failed to open scene. {e.message}") from e

    assert {obj.id for obj in glob.SCENE.objects} == glob.SCENE_OBJECT_INSTANCES.keys()


def get_instance(obj_id: str) -> Generic:

    if obj_id not in glob.SCENE_OBJECT_INSTANCES:
        raise Arcor2Exception("Unknown object/service ID.")

    return glob.SCENE_OBJECT_INSTANCES[obj_id]
