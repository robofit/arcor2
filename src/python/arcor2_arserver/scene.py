import asyncio
from typing import AsyncIterator, Dict, List, Optional, Set

from arcor2 import helpers as hlp
from arcor2.cached import CachedScene, UpdateableCachedScene
from arcor2.clients import aio_scene_service as scene_srv
from arcor2.data.common import Parameter, Pose, SceneObject
from arcor2.data.events import Event
from arcor2.data.object_type import Models
from arcor2.exceptions import Arcor2Exception
from arcor2.object_types.abstract import Generic, GenericWithPose, Robot
from arcor2.object_types.utils import settings_from_params
from arcor2_arserver import globals as glob
from arcor2_arserver import notifications as notif
from arcor2_arserver.clients import persistent_storage as storage
from arcor2_arserver.object_types.data import ObjectTypeData
from arcor2_arserver.objects_actions import get_object_types
from arcor2_arserver_data.events.common import ShowMainScreen
from arcor2_arserver_data.events.scene import SceneClosed, SceneObjectChanged, SceneState

# TODO maybe this could be property of ARServerScene(CachedScene)?
_scene_state: SceneState.Data.StateEnum = SceneState.Data.StateEnum.Stopped


async def update_scene_object_pose(
    obj: SceneObject, pose: Optional[Pose] = None, obj_inst: Optional[GenericWithPose] = None
) -> None:
    """Performs all necessary actions when pose of an object is updated.

    :param obj:
    :param pose:
    :param obj_inst:
    :return:
    """

    assert glob.SCENE

    if pose:
        # SceneObject pose was not updated before
        obj.pose = pose
    else:
        # SceneObject pose was already updated
        pose = obj.pose

    glob.SCENE.update_modified()

    evt = SceneObjectChanged(obj)
    evt.change_type = Event.Type.UPDATE
    await notif.broadcast_event(evt)

    glob.OBJECTS_WITH_UPDATED_POSE.add(obj.id)

    if scene_started():

        if obj_inst is None:
            inst = get_instance(obj.id)
            assert isinstance(inst, GenericWithPose)
            obj_inst = inst

        assert pose is not None

        # Object pose is property that might call scene service - that's why it has to be called using executor.
        await hlp.run_in_executor(setattr, obj_inst, "pose", pose)


async def set_scene_state(state: SceneState.Data.StateEnum, message: Optional[str] = None) -> None:

    global _scene_state
    _scene_state = state
    await notif.broadcast_event(SceneState(SceneState.Data(state, message)))


def get_scene_state() -> SceneState.Data.StateEnum:
    return _scene_state


def scene_started() -> bool:
    return _scene_state == SceneState.Data.StateEnum.Started


def can_modify_scene() -> None:
    """Raises exception if modifications to scene/project are not possible."""

    if _scene_state != SceneState.Data.StateEnum.Stopped:
        raise Arcor2Exception("Modification can be only done in stopped state.")


def ensure_scene_started() -> None:
    """" Raises exception if scene is not started."""

    if _scene_state != SceneState.Data.StateEnum.Started:
        raise Arcor2Exception("Scene not started.")


async def scenes() -> AsyncIterator[CachedScene]:

    for scene_id in (await storage.get_scenes()).items:
        yield CachedScene(await storage.get_scene(scene_id.id))


async def scene_names() -> Set[str]:
    return {scene.name for scene in (await storage.get_scenes()).items}


async def notify_scene_closed(scene_id: str) -> None:

    await notif.broadcast_event(SceneClosed())
    glob.MAIN_SCREEN = ShowMainScreen.Data(ShowMainScreen.Data.WhatEnum.ScenesList)
    await notif.broadcast_event(
        ShowMainScreen(data=ShowMainScreen.Data(ShowMainScreen.Data.WhatEnum.ScenesList, scene_id))
    )


def check_object_parameters(obj_type: ObjectTypeData, parameters: List[Parameter]) -> None:

    if {s.name for s in obj_type.meta.settings if s.default_value is None} > {s.name for s in parameters}:
        raise Arcor2Exception("Some required parameter is missing.")

    # TODO check types of parameters, ranges, etc.


def check_object(obj: SceneObject, new_one: bool = False) -> None:
    """Checks if object can be added into the scene."""

    assert glob.SCENE
    assert not obj.children

    if obj.type not in glob.OBJECT_TYPES:
        raise Arcor2Exception("Unknown object type.")

    obj_type = glob.OBJECT_TYPES[obj.type]

    if obj_type.meta.disabled:
        raise Arcor2Exception("Object type disabled.")

    check_object_parameters(obj_type, obj.parameters)

    # TODO check whether object needs parent and if so, if the parent is in scene and parent_id is set
    if obj_type.meta.needs_parent_type:
        pass

    if obj_type.meta.has_pose and obj.pose is None:
        raise Arcor2Exception("Object requires pose.")

    if not obj_type.meta.has_pose and obj.pose is not None:
        raise Arcor2Exception("Object do not have pose.")

    if obj_type.meta.abstract:
        raise Arcor2Exception("Cannot instantiate abstract type.")

    if new_one:

        if obj.id in glob.SCENE.object_ids:
            raise Arcor2Exception("Object/service with that id already exists.")

        if obj.name in glob.SCENE.object_names():
            raise Arcor2Exception("Name is already used.")

    hlp.is_valid_identifier(obj.name)


async def add_object_to_scene(obj: SceneObject, dry_run: bool = False) -> None:
    """

    :param obj:
    :param add_to_scene: Set to false to only create object instance and add its collision model (if any).
    :return:
    """

    assert glob.SCENE

    check_object(obj, new_one=True)

    if dry_run:
        return None

    glob.SCENE.upsert_object(obj)
    glob.logger.debug(f"Object {obj.id} ({obj.type}) added to scene.")


async def create_object_instance(obj: SceneObject, overrides: Optional[List[Parameter]] = None) -> None:

    obj_type = glob.OBJECT_TYPES[obj.type]

    # settings -> dataclass
    assert obj_type.type_def
    glob.logger.debug(
        f"Creating instance of {obj_type.type_def.__name__} with name {obj.name}. "
        f"Parameters: {obj.parameters}, overrides: {overrides}."
    )
    settings = settings_from_params(obj_type.type_def, obj.parameters, overrides)

    assert obj_type.type_def is not None

    try:

        try:

            if issubclass(obj_type.type_def, Robot):
                assert obj.pose is not None
                glob.SCENE_OBJECT_INSTANCES[obj.id] = await hlp.run_in_executor(
                    obj_type.type_def, obj.id, obj.name, obj.pose, settings
                )
            elif issubclass(obj_type.type_def, GenericWithPose):
                assert obj.pose is not None
                coll_model: Optional[Models] = None
                if obj_type.meta.object_model:
                    coll_model = obj_type.meta.object_model.model()

                glob.SCENE_OBJECT_INSTANCES[obj.id] = await hlp.run_in_executor(
                    obj_type.type_def, obj.id, obj.name, obj.pose, coll_model, settings
                )

            elif issubclass(obj_type.type_def, Generic):
                assert obj.pose is None
                glob.SCENE_OBJECT_INSTANCES[obj.id] = await hlp.run_in_executor(
                    obj_type.type_def, obj.id, obj.name, settings
                )

            else:
                raise Arcor2Exception("Object type with unknown base.")

        except (TypeError, ValueError) as e:  # catch some most often exceptions
            raise Arcor2Exception("Unhandled error.") from e

    except Arcor2Exception as e:
        # make the exception a bit more user-friendly by including the object's name
        raise Arcor2Exception(f"Failed to initialize {obj.name}. {str(e)}") from e

    return None


async def open_scene(scene_id: str) -> None:

    await get_object_types()
    asyncio.ensure_future(scene_srv.delete_all_collisions())
    glob.SCENE = UpdateableCachedScene(await storage.get_scene(scene_id))

    try:
        for obj in glob.SCENE.objects:
            check_object(obj)
    except Arcor2Exception as e:
        glob.SCENE = None
        raise Arcor2Exception(f"Failed to open scene. {str(e)}") from e


# TODO optional parameter for expected return type
def get_instance(obj_id: str) -> Generic:

    if obj_id not in glob.SCENE_OBJECT_INSTANCES:
        raise Arcor2Exception("Unknown object/service ID.")

    return glob.SCENE_OBJECT_INSTANCES[obj_id]


async def cleanup_object(obj: Generic) -> None:

    try:
        await hlp.run_in_executor(obj.cleanup)
    except Arcor2Exception as e:
        # make the exception a bit more user-friendly by including the object's name
        raise Arcor2Exception(f"Failed to cleanup {obj.name}. {str(e)}") from e


async def stop_scene(message: Optional[str] = None) -> None:
    """Destroys scene object instances."""

    glob.logger.info("Stopping the scene.")

    await set_scene_state(SceneState.Data.StateEnum.Stopping, message)

    if await scene_srv.started():
        try:
            await scene_srv.stop()
        except Arcor2Exception as e:
            glob.logger.exception("Failed to stop the scene.")
            await set_scene_state(SceneState.Data.StateEnum.Started, str(e))
            return

    try:
        await asyncio.gather(*[cleanup_object(obj) for obj in glob.SCENE_OBJECT_INSTANCES.values()])
    except Arcor2Exception as e:
        glob.logger.exception("Exception occurred while cleaning up objects.")
        await set_scene_state(SceneState.Data.StateEnum.Stopped, str(e))
    else:
        await set_scene_state(SceneState.Data.StateEnum.Stopped)

    glob.SCENE_OBJECT_INSTANCES.clear()


async def start_scene() -> None:
    """Creates instances of scene objects."""

    glob.logger.info("Starting the scene.")

    assert glob.SCENE

    await set_scene_state(SceneState.Data.StateEnum.Starting)

    try:
        await scene_srv.stop()
    except Arcor2Exception:
        await set_scene_state(SceneState.Data.StateEnum.Stopped, "Failed to prepare for start.")
        return

    object_overrides: Dict[str, List[Parameter]] = {}

    if glob.PROJECT:
        object_overrides = glob.PROJECT.overrides

    # object initialization could take some time - let's do it in parallel
    tasks = [
        asyncio.ensure_future(
            create_object_instance(obj, object_overrides[obj.id] if obj.id in object_overrides else None)
        )
        for obj in glob.SCENE.objects
    ]

    try:
        await asyncio.gather(*tasks)
    except Arcor2Exception as e:
        for t in tasks:
            t.cancel()
        glob.logger.exception("Failed to create instances.")
        await stop_scene(str(e))
        return

    try:
        await scene_srv.start()
    except Arcor2Exception as e:
        glob.logger.exception("Failed to start scene.")
        await stop_scene(str(e))
        return

    await set_scene_state(SceneState.Data.StateEnum.Started)
    assert scene_started()
    assert await scene_srv.started()
