import asyncio
from dataclasses import dataclass
from datetime import datetime
from typing import AsyncIterator, TypeVar

from arcor2 import helpers as hlp
from arcor2.cached import CachedScene, UpdateableCachedScene
from arcor2.clients import aio_scene_service as scene_srv
from arcor2.data.common import Parameter, Pose, SceneObject
from arcor2.data.events import Event
from arcor2.data.object_type import Models
from arcor2.exceptions import Arcor2Exception
from arcor2.object_types.abstract import CollisionObject, Generic, GenericWithPose, Robot, VirtualCollisionObject
from arcor2.object_types.utils import settings_from_params
from arcor2_arserver import globals as glob
from arcor2_arserver import logger
from arcor2_arserver import notifications as notif
from arcor2_arserver.checks import check_object, scene_problems
from arcor2_arserver.clients import project_service as storage
from arcor2_arserver.common import invalidate_joints_using_object_as_parent
from arcor2_arserver.helpers import ctx_write_lock
from arcor2_arserver.lock.exceptions import CannotLock
from arcor2_arserver.object_types.utils import remove_object_type
from arcor2_arserver.objects_actions import get_object_types
from arcor2_arserver_data import events as sevts
from arcor2_arserver_data.events.common import ShowMainScreen
from arcor2_arserver_data.events.scene import OpenScene, SceneClosed, SceneObjectChanged, SceneState
from arcor2_arserver_data.objects import ObjectTypeMeta

# TODO maybe this could be property of ARServerScene(CachedScene)?
_scene_state: SceneState = SceneState(SceneState.Data(SceneState.Data.StateEnum.Stopped))


@dataclass
class SceneProblems:
    scene_modified: datetime
    problems: list[str]
    ot_modified: dict[str, datetime]


_scene_problems: dict[str, SceneProblems] = {}
_objects_to_auto_remove: set[str] = set()


async def schedule_auto_remove(obj_type: str) -> None:
    logger.debug(f"OT {obj_type} scheduled to be autoremoved.")
    _objects_to_auto_remove.add(obj_type)


async def clear_auto_remove_schedule() -> None:
    logger.debug(f"Auto-remove schedule will be cleared. It contained: {_objects_to_auto_remove}")
    _objects_to_auto_remove.clear()


async def scheduled_to_be_auto_removed() -> set[str]:
    return _objects_to_auto_remove


async def unschedule_auto_remove(obj_type: str) -> None:

    try:
        _objects_to_auto_remove.remove(obj_type)
    except KeyError:
        pass
    else:
        logger.debug(f"OT {obj_type} unscheduled to be auto-removed.")


async def remove_scheduled() -> None:

    logger.debug(f"Going to auto-remove following types: {_objects_to_auto_remove}")
    for ot_id in _objects_to_auto_remove:
        if ot_id in glob.OBJECT_TYPES:
            asyncio.create_task(delete_if_not_used(glob.OBJECT_TYPES[ot_id].meta))
    _objects_to_auto_remove.clear()


async def delete_if_not_used(meta: ObjectTypeMeta) -> None:

    if meta.base != VirtualCollisionObject.__name__:
        logger.debug(f"{meta.type} is not a VCO!")
        return

    assert meta.object_model
    assert meta.type == meta.object_model.model().id, f"meta.type={meta.type}, model.id={meta.object_model.model().id}"

    async for scn in scenes():
        if any(scn.objects_of_type(meta.type)):
            logger.debug(f"Not auto-removing VCO {meta.type} as it is used in scene {scn.name}.")
            return

    logger.debug(f"Auto-removing VCO {meta.type} as it is not used in any scene.")

    try:
        await asyncio.gather(
            storage.delete_object_type(meta.type),
            storage.delete_model(meta.type),
            remove_object_type(meta.type),
        )
    except Arcor2Exception as e:
        logger.warn(str(e))

    del glob.OBJECT_TYPES[meta.type]

    logger.debug(f"Auto-removing {meta.type} done... {meta}")

    evtr = sevts.o.ChangedObjectTypes([meta])
    evtr.change_type = Event.Type.REMOVE
    await notif.broadcast_event(evtr)


async def save_scene(scene: None | UpdateableCachedScene = None) -> None:

    if not scene:
        scene = glob.LOCK.scene_or_exception()

    scene.modified = await storage.update_scene(scene)
    asyncio.ensure_future(notif.broadcast_event(sevts.s.SceneSaved()))
    asyncio.create_task(remove_scheduled())

    for obj_id in glob.OBJECTS_WITH_UPDATED_POSE:
        asyncio.ensure_future(invalidate_joints_using_object_as_parent(scene.object(obj_id)))
    glob.OBJECTS_WITH_UPDATED_POSE.clear()


def get_ot_modified(ots: set[str]) -> dict[str, datetime]:
    return {k: v.meta.modified for k, v in glob.OBJECT_TYPES.items() if k in ots and v.meta.modified is not None}


async def get_scene_problems(scene: CachedScene) -> None | list[str]:
    """Handle caching of scene problems."""

    assert scene.modified

    ots = scene.object_types
    await get_object_types()
    ot_modified = get_ot_modified(ots)

    if (
        scene.id not in _scene_problems
        or _scene_problems[scene.id].scene_modified < scene.modified
        or _scene_problems[scene.id].ot_modified != ot_modified
    ):

        logger.debug(f"Updating scene_problems for {scene.name}.")

        _scene_problems[scene.id] = SceneProblems(
            scene.modified,
            scene_problems(glob.OBJECT_TYPES, scene),
            get_ot_modified(ots),
        )

    # prune removed scenes
    for csi in set(_scene_problems.keys()) - await storage.get_scene_ids():
        logger.debug(f"Pruning cached problems for removed scene {csi}.")
        _scene_problems.pop(csi, None)

    sp = _scene_problems[scene.id].problems

    return sp if sp else None


async def update_scene_object_pose(
    scene: UpdateableCachedScene,
    obj: SceneObject,
    pose: None | Pose = None,
    obj_inst: None | GenericWithPose = None,
    lock_owner: None | str = None,
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
            obj_inst = get_instance(obj.id, GenericWithPose)

        assert pose is not None

        # Object pose is property that might call scene service - that's why it has to be called using executor.
        await hlp.run_in_executor(setattr, obj_inst, "pose", pose)

    if lock_owner:
        await glob.LOCK.write_unlock(obj.id, lock_owner, True)


async def set_scene_state(state: SceneState.Data.StateEnum, message: None | str = None) -> None:

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
    """Raises exception if scene is not started."""

    if _scene_state.data.state != SceneState.Data.StateEnum.Started:
        raise Arcor2Exception("Scene offline.")


async def notify_scene_opened(evt: OpenScene) -> None:

    await notif.broadcast_event(evt)
    ss = get_scene_state()
    assert ss.data.state == ss.Data.StateEnum.Stopped
    await notif.broadcast_event(ss)


async def scenes() -> AsyncIterator[CachedScene]:

    for scene_id in await storage.get_scene_ids():
        yield await storage.get_scene(scene_id)


async def scene_names() -> set[str]:
    return {scene.name for scene in (await storage.get_scenes())}


async def notify_scene_closed(scene_id: str) -> None:

    assert get_scene_state().data.state == SceneState.Data.StateEnum.Stopped

    await notif.broadcast_event(SceneClosed())
    glob.MAIN_SCREEN = ShowMainScreen.Data(ShowMainScreen.Data.WhatEnum.ScenesList)
    await notif.broadcast_event(
        ShowMainScreen(data=ShowMainScreen.Data(ShowMainScreen.Data.WhatEnum.ScenesList, scene_id))
    )


async def add_object_to_scene(scene: UpdateableCachedScene, obj: SceneObject, dry_run: bool = False) -> None:
    """

    :param obj:
    :param add_to_scene: Set to false to only create object instance and add its collision model (if any).
    :return:
    """

    check_object(glob.OBJECT_TYPES, scene, obj, new_one=True)

    if dry_run:
        return None

    scene.upsert_object(obj)
    logger.debug(f"Object {obj.id} ({obj.type}) added to scene.")


async def create_object_instance(obj: SceneObject, overrides: None | list[Parameter] = None) -> None:

    obj_type = glob.OBJECT_TYPES[obj.type]

    # settings -> dataclass
    assert obj_type.type_def
    logger.debug(
        f"Creating instance of {obj_type.type_def.__name__} with name {obj.name}. "
        f"Parameters: {obj.parameters}, overrides: {overrides}."
    )
    settings = settings_from_params(obj_type.type_def, obj.parameters, overrides)

    assert obj_type.type_def is not None

    try:

        try:

            # the order must be from specific to the generic types
            if issubclass(obj_type.type_def, Robot):
                assert obj.pose is not None
                glob.SCENE_OBJECT_INSTANCES[obj.id] = await hlp.run_in_executor(
                    obj_type.type_def, obj.id, obj.name, obj.pose, settings
                )
            elif issubclass(obj_type.type_def, CollisionObject):
                assert obj.pose is not None
                coll_model: None | Models = None
                if obj_type.meta.object_model:
                    coll_model = obj_type.meta.object_model.model()

                glob.SCENE_OBJECT_INSTANCES[obj.id] = await hlp.run_in_executor(
                    obj_type.type_def, obj.id, obj.name, obj.pose, coll_model, settings
                )
            elif issubclass(obj_type.type_def, GenericWithPose):
                assert obj.pose is not None

                glob.SCENE_OBJECT_INSTANCES[obj.id] = await hlp.run_in_executor(
                    obj_type.type_def, obj.id, obj.name, obj.pose, settings
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

    scene = await storage.get_scene(scene_id)

    if sp := await get_scene_problems(scene):  # this also refreshes ObjectTypes / calls get_object_types()
        logger.warning(f"Scene {scene.name} can't be opened due to the following problem(s)...")
        for spp in sp:
            logger.warning(spp)
        raise Arcor2Exception("Scene has some problems.")

    glob.LOCK.scene = UpdateableCachedScene(scene)


def get_robot_instance(obj_id: str) -> Robot:  # TODO remove once https://github.com/python/mypy/issues/5374 is solved

    robot_inst = get_instance(obj_id, Robot)  # type: ignore
    assert isinstance(robot_inst, Robot)
    return robot_inst


T = TypeVar("T", bound=Generic)


# TODO "thanks" to https://github.com/python/mypy/issues/3737, `expected_type: type[T] = Generic` can't be used
def get_instance(obj_id: str, expected_type: type[T]) -> T:

    assert scene_started()

    try:
        inst = glob.SCENE_OBJECT_INSTANCES[obj_id]
    except KeyError:
        raise Arcor2Exception("Unknown object ID.")

    if not isinstance(inst, expected_type):
        raise Arcor2Exception(f"{inst.name} is not of {expected_type.__name__} type.")

    return inst


async def cleanup_object(obj: Generic) -> None:

    try:
        await hlp.run_in_executor(obj.cleanup)
    except Arcor2Exception as e:
        # make the exception a bit more user-friendly by including the object's name
        raise Arcor2Exception(f"Failed to cleanup {obj.name}. {str(e)}") from e


async def stop_scene(scene: CachedScene, message: None | str = None, already_locked: bool = False) -> None:
    """Destroys scene object instances."""

    async def _stop_scene() -> None:

        await set_scene_state(SceneState.Data.StateEnum.Stopping, message)

        try:
            await scene_srv.stop()
        except Arcor2Exception as e:
            logger.exception("Failed to go offline.")
            await set_scene_state(SceneState.Data.StateEnum.Started, str(e))
            return

        try:
            await asyncio.gather(*[cleanup_object(obj) for obj in glob.SCENE_OBJECT_INSTANCES.values()])
        except Arcor2Exception as e:
            logger.exception("Exception occurred while cleaning up objects.")
            await set_scene_state(SceneState.Data.StateEnum.Stopped, str(e))
        else:
            await set_scene_state(SceneState.Data.StateEnum.Stopped)

        glob.SCENE_OBJECT_INSTANCES.clear()
        glob.PREV_RESULTS.clear()

    if already_locked:

        logger.info(f"Stopping the {scene.name} scene after unsuccessful start.")

        assert await glob.LOCK.is_write_locked(glob.LOCK.SpecialValues.SCENE, glob.LOCK.Owners.SERVER)
        assert (glob.LOCK.project is not None) == await glob.LOCK.is_write_locked(
            glob.LOCK.SpecialValues.PROJECT, glob.LOCK.Owners.SERVER
        )

        await _stop_scene()
    else:

        to_lock = [glob.LOCK.SpecialValues.SCENE]

        if glob.LOCK.project:
            to_lock.append(glob.LOCK.SpecialValues.PROJECT)

        try:
            async with ctx_write_lock(to_lock, glob.LOCK.Owners.SERVER):
                logger.info(f"Stopping the {scene.name} scene.")
                await _stop_scene()
        except CannotLock:
            logger.warning(f"Failed attempt to stop the scene. Can't lock {to_lock}.")
            return
        except Arcor2Exception as e:
            logger.error(f"Failed to stop the scene. {str(e)}")
            return

    assert not scene_started()
    assert not await scene_srv.started()

    logger.info("Scene stopped.")


async def start_scene(scene: CachedScene) -> None:
    """Creates instances of scene objects."""

    async def _start_scene() -> bool:

        logger.info(f"Starting the {scene.name} scene.")

        await set_scene_state(SceneState.Data.StateEnum.Starting)

        # in order to prepare a clear environment
        try:
            # stop deletes all configurations and clears all collisions
            await scene_srv.stop()
        except Arcor2Exception:
            logger.exception("Failed to prepare for start.")
            await set_scene_state(SceneState.Data.StateEnum.Stopped, "Failed to prepare for start.")
            return False

        object_overrides: dict[str, list[Parameter]] = {}

        if glob.LOCK.project:
            object_overrides = glob.LOCK.project.overrides

        # object initialization could take some time - let's do it in parallel
        tasks = [
            asyncio.ensure_future(
                create_object_instance(obj, object_overrides[obj.id] if obj.id in object_overrides else None)
            )
            for obj in scene.objects
        ]

        try:
            await asyncio.gather(*tasks)
        except Arcor2Exception as e:
            for t in tasks:
                t.cancel()  # TODO maybe it would be better to let them finish?
            logger.exception("Failed to create instances.")
            await stop_scene(scene, str(e), already_locked=True)
            return False

        try:
            await scene_srv.start()
        except Arcor2Exception as e:
            logger.exception("Failed to go online.")
            await stop_scene(scene, str(e), already_locked=True)
            return False

        await set_scene_state(SceneState.Data.StateEnum.Started)
        return True

    to_lock = [glob.LOCK.SpecialValues.SCENE]

    if glob.LOCK.project:
        to_lock.append(glob.LOCK.SpecialValues.PROJECT)

    try:
        async with ctx_write_lock(to_lock, glob.LOCK.Owners.SERVER):
            ret = await _start_scene()
    except CannotLock:
        logger.warning(f"Failed attempt to start the scene. Can't lock {to_lock}.")
        return
    except Arcor2Exception as e:
        logger.error(f"Failed to start the scene. {str(e)}")

    assert ret == scene_started()
    assert ret == await scene_srv.started()

    if ret:
        logger.info("Scene started. Enjoy!")
