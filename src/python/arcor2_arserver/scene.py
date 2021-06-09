import asyncio
from collections import defaultdict
from typing import AsyncIterator, DefaultDict, Dict, List, Optional, Set

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
from arcor2_arserver.clients import project_service as storage
from arcor2_arserver.helpers import ctx_write_lock
from arcor2_arserver.object_types.data import ObjectTypeData
from arcor2_arserver.objects_actions import get_object_types
from arcor2_arserver_data.events.common import ShowMainScreen
from arcor2_arserver_data.events.scene import OpenScene, SceneClosed, SceneObjectChanged, SceneState

# TODO maybe this could be property of ARServerScene(CachedScene)?
_scene_state: SceneState = SceneState(SceneState.Data(SceneState.Data.StateEnum.Stopped))


async def update_scene_object_pose(
    scene: UpdateableCachedScene,
    obj: SceneObject,
    pose: Optional[Pose] = None,
    obj_inst: Optional[GenericWithPose] = None,
    lock_owner: Optional[str] = None,
) -> None:
    """Performs all necessary actions when pose of an object is updated.

    :param obj:
    :param pose:
    :param obj_inst:
    :param lock_owner: if present, object is unlocked at the end of function
    :return:
    """

    if pose:
        # SceneObject pose was not updated before
        obj.pose = pose
    else:
        # SceneObject pose was already updated
        pose = obj.pose

    scene.update_modified()

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

    if lock_owner:
        await glob.LOCK.read_unlock(obj.id, lock_owner)


async def set_scene_state(state: SceneState.Data.StateEnum, message: Optional[str] = None) -> None:

    global _scene_state
    _scene_state = SceneState(SceneState.Data(state, message))
    asyncio.create_task(notif.broadcast_event(_scene_state))


def get_scene_state() -> SceneState:
    return _scene_state


def scene_started() -> bool:
    return _scene_state.data.state == SceneState.Data.StateEnum.Started


def can_modify_scene() -> None:
    """Raises exception if modifications to scene/project are not possible."""

    if _scene_state.data.state != SceneState.Data.StateEnum.Stopped:
        raise Arcor2Exception("Modifications can be only done offline.")


def ensure_scene_started() -> None:
    """" Raises exception if scene is not started."""

    if _scene_state.data.state != SceneState.Data.StateEnum.Started:
        raise Arcor2Exception("Scene offline.")


async def notify_scene_opened(evt: OpenScene) -> None:

    await notif.broadcast_event(evt)
    ss = get_scene_state()
    assert ss.data.state == ss.Data.StateEnum.Stopped
    await notif.broadcast_event(ss)


async def scenes() -> AsyncIterator[CachedScene]:

    for scene_id in await storage.get_scene_ids():
        yield CachedScene(await storage.get_scene(scene_id))


async def scene_names() -> Set[str]:
    return {scene.name for scene in (await storage.get_scenes())}


async def notify_scene_closed(scene_id: str) -> None:

    assert get_scene_state().data.state == SceneState.Data.StateEnum.Stopped

    await notif.broadcast_event(SceneClosed())
    glob.MAIN_SCREEN = ShowMainScreen.Data(ShowMainScreen.Data.WhatEnum.ScenesList)
    await notif.broadcast_event(
        ShowMainScreen(data=ShowMainScreen.Data(ShowMainScreen.Data.WhatEnum.ScenesList, scene_id))
    )


def check_object_parameters(obj_type: ObjectTypeData, parameters: List[Parameter]) -> None:

    if {s.name for s in obj_type.meta.settings if s.default_value is None} > {s.name for s in parameters}:
        raise Arcor2Exception("Some required parameter is missing.")

    # TODO check types of parameters, ranges, etc.


def check_object(scene: CachedScene, obj: SceneObject, new_one: bool = False) -> None:
    """Checks if object can be added into the scene."""

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

        if obj.id in scene.object_ids:
            raise Arcor2Exception("Object/service with that id already exists.")

        if obj.name in scene.object_names():
            raise Arcor2Exception("Name is already used.")

    hlp.is_valid_identifier(obj.name)


async def add_object_to_scene(scene: UpdateableCachedScene, obj: SceneObject, dry_run: bool = False) -> None:
    """

    :param obj:
    :param add_to_scene: Set to false to only create object instance and add its collision model (if any).
    :return:
    """

    check_object(scene, obj, new_one=True)

    if dry_run:
        return None

    scene.upsert_object(obj)
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
    glob.LOCK.scene = UpdateableCachedScene(await storage.get_scene(scene_id))

    try:
        for obj in glob.LOCK.scene.objects:
            check_object(glob.LOCK.scene, obj)
    except Arcor2Exception as e:
        glob.LOCK.scene = None
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


async def stop_scene(scene: CachedScene, message: Optional[str] = None, already_locked: bool = False) -> None:
    """Destroys scene object instances."""

    async def _stop_scene() -> None:

        await set_scene_state(SceneState.Data.StateEnum.Stopping, message)

        if await scene_srv.started():
            try:
                await scene_srv.stop()
            except Arcor2Exception as e:
                glob.logger.exception("Failed to go offline.")
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
        glob.PREV_RESULTS.clear()

    if already_locked:

        glob.logger.info(f"Stopping the {scene.name} scene after unsuccessful start.")

        assert await glob.LOCK.is_write_locked(glob.LOCK.SpecialValues.SCENE_NAME, glob.LOCK.SpecialValues.SERVER_NAME)
        assert (glob.LOCK.project is not None) == await glob.LOCK.is_write_locked(
            glob.LOCK.SpecialValues.PROJECT_NAME, glob.LOCK.SpecialValues.SERVER_NAME
        )

        await _stop_scene()
    else:

        glob.logger.info(f"Stopping the {scene.name} scene.")

        assert not await glob.LOCK.is_write_locked(
            glob.LOCK.SpecialValues.SCENE_NAME, glob.LOCK.SpecialValues.SERVER_NAME
        )
        assert not await glob.LOCK.is_write_locked(
            glob.LOCK.SpecialValues.PROJECT_NAME, glob.LOCK.SpecialValues.SERVER_NAME
        )

        to_lock = [glob.LOCK.SpecialValues.SCENE_NAME]

        if glob.LOCK.project:
            assert not await glob.LOCK.is_write_locked(
                glob.LOCK.SpecialValues.PROJECT_NAME, glob.LOCK.SpecialValues.SERVER_NAME
            )
            to_lock.append(glob.LOCK.SpecialValues.PROJECT_NAME)

        try:
            async with ctx_write_lock(to_lock, glob.LOCK.SpecialValues.SERVER_NAME):
                await _stop_scene()
        except Arcor2Exception as e:
            glob.logger.error(f"Failed to stop the scene. {str(e)}")
            return

    assert not scene_started()
    assert not await scene_srv.started()

    glob.logger.info("Scene stopped.")


async def start_scene(scene: CachedScene) -> None:
    """Creates instances of scene objects."""

    async def _start_scene() -> bool:

        glob.logger.info(f"Starting the {scene.name} scene.")

        await set_scene_state(SceneState.Data.StateEnum.Starting)

        try:
            await scene_srv.stop()
        except Arcor2Exception:
            await set_scene_state(SceneState.Data.StateEnum.Stopped, "Failed to prepare for start.")
            return False

        object_overrides: Dict[str, List[Parameter]] = {}

        if glob.LOCK.project:
            object_overrides = glob.LOCK.project.overrides

        prio_dict: DefaultDict[int, List[SceneObject]] = defaultdict(list)

        for obj in scene.objects:
            type_def = glob.OBJECT_TYPES[obj.type].type_def
            assert type_def
            prio_dict[type_def.INIT_PRIORITY].append(obj)

        for prio in sorted(prio_dict.keys(), reverse=True):

            assert prio_dict[prio]

            # object initialization could take some time - let's do it in parallel (grouped by priority)
            tasks = [
                asyncio.ensure_future(
                    create_object_instance(obj, object_overrides[obj.id] if obj.id in object_overrides else None)
                )
                for obj in prio_dict[prio]
            ]

            try:
                await asyncio.gather(*tasks)
            except Arcor2Exception as e:
                for t in tasks:
                    t.cancel()
                glob.logger.exception("Failed to create instances.")
                await stop_scene(scene, str(e), already_locked=True)
                return False

        try:
            await scene_srv.start()
        except Arcor2Exception as e:
            glob.logger.exception("Failed to go online.")
            await stop_scene(scene, str(e), already_locked=True)
            return False

        await set_scene_state(SceneState.Data.StateEnum.Started)
        return True

    to_lock = [glob.LOCK.SpecialValues.SCENE_NAME]

    if glob.LOCK.project:
        to_lock.append(glob.LOCK.SpecialValues.PROJECT_NAME)

    try:
        async with ctx_write_lock(to_lock, glob.LOCK.SpecialValues.SERVER_NAME):
            ret = await _start_scene()
    except Arcor2Exception as e:
        glob.logger.error(f"Failed to start the scene. {str(e)}")
        return

    assert ret == scene_started()
    assert ret == await scene_srv.started()

    glob.logger.info("Scene started.")
