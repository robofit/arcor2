import asyncio
import os
from typing import Optional, Type

from arcor2 import helpers as hlp
from arcor2.clients import aio_persistent_storage as ps
from arcor2.data.events import Event
from arcor2.data.object_type import ObjectModel
from arcor2.exceptions import Arcor2Exception
from arcor2.object_types import utils as otu
from arcor2.object_types.abstract import Generic, Robot
from arcor2.object_types.utils import built_in_types_names, get_containing_module_sources, prepare_object_types_dir
from arcor2.parameter_plugins.base import TypesDict
from arcor2.source.utils import parse
from arcor2_arserver import globals as glob
from arcor2_arserver import notifications as notif
from arcor2_arserver import settings
from arcor2_arserver.clients import persistent_storage as storage
from arcor2_arserver.object_types.utils import (
    ObjectTypeData,
    ObjectTypeDict,
    add_ancestor_actions,
    built_in_types_data,
    meta_from_def,
    obj_description_from_base,
    object_actions,
    remove_object_type,
)
from arcor2_arserver.robot import get_robot_meta
from arcor2_arserver_data.events.objects import ChangedObjectTypes
from arcor2_arserver_data.objects import ObjectTypeMeta


def get_types_dict() -> TypesDict:

    return {k: v.type_def for k, v in glob.OBJECT_TYPES.items() if v.type_def is not None}


def get_obj_type_name(object_id: str) -> str:

    assert glob.SCENE

    try:
        return glob.SCENE.object(object_id).type
    except KeyError:
        raise Arcor2Exception("Unknown object id.")


def get_obj_type_data(object_id: str) -> ObjectTypeData:

    try:
        return glob.OBJECT_TYPES[get_obj_type_name(object_id)]
    except KeyError:
        raise Arcor2Exception("Unknown object type.")


def valid_object_types() -> ObjectTypeDict:
    """To get only valid (not disabled) types.

    :return:
    """

    return {obj_type: obj for obj_type, obj in glob.OBJECT_TYPES.items() if not obj.meta.disabled}


async def handle_robot_urdf(robot: Type[Robot]) -> None:

    if not robot.urdf_package_name:
        return

    file_path = os.path.join(settings.URDF_PATH, robot.urdf_package_name)

    try:
        await ps.save_mesh_file(robot.urdf_package_name, file_path)
    except Arcor2Exception:
        glob.logger.exception(f"Failed to download URDF for {robot.__name__}.")


async def get_object_data(object_types: ObjectTypeDict, obj_id: str) -> None:

    glob.logger.debug(f"Processing {obj_id}.")

    if obj_id in object_types:
        glob.logger.debug(f"{obj_id} already processed, skipping...")
        return

    obj = await storage.get_object_type(obj_id)

    if obj_id in glob.OBJECT_TYPES and glob.OBJECT_TYPES[obj_id].type_def is not None:

        stored_type_def = glob.OBJECT_TYPES[obj_id].type_def
        assert stored_type_def
        if hash(get_containing_module_sources(stored_type_def)) == hash(obj.source):
            glob.logger.debug(f"No need to update {obj_id}.")
            return

    try:
        base = otu.base_from_source(obj.source, obj_id)
        if base and base not in object_types.keys() | built_in_types_names():
            glob.logger.debug(f"Getting base class {base} for {obj_id}.")
            await get_object_data(object_types, base)
    except Arcor2Exception:
        object_types[obj_id] = ObjectTypeData(
            ObjectTypeMeta(obj_id, "Object type disabled.", disabled=True, problem="Can't get base.")
        )
        return

    glob.logger.debug(f"Updating {obj_id}.")

    try:
        type_def = await hlp.run_in_executor(
            hlp.save_and_import_type_def,
            obj.source,
            obj.id,
            Generic,
            settings.OBJECT_TYPE_PATH,
            settings.OBJECT_TYPE_MODULE,
        )
        assert issubclass(type_def, Generic)
        meta = meta_from_def(type_def)
        otu.get_settings_def(type_def)  # just to check if settings are ok
    except Arcor2Exception as e:
        glob.logger.warning(f"Disabling object type {obj.id}.")
        glob.logger.debug(e, exc_info=True)
        object_types[obj_id] = ObjectTypeData(
            ObjectTypeMeta(obj_id, "Object type disabled.", disabled=True, problem=str(e))
        )
        return

    if obj.model:
        try:
            model = await storage.get_model(obj.model.id, obj.model.type)
        except Arcor2Exception:
            glob.logger.error(f"{obj.model.id}: failed to get collision model of type {obj.model.type}.")
            meta.disabled = True
            meta.problem = "Can't get collision model."
            object_types[obj_id] = ObjectTypeData(meta)
            return

        kwargs = {model.type().value.lower(): model}
        meta.object_model = ObjectModel(model.type(), **kwargs)  # type: ignore

    ast = parse(obj.source)
    otd = ObjectTypeData(meta, type_def, object_actions(type_def, ast), ast)

    object_types[obj_id] = otd


async def get_object_types() -> None:
    """Serves to initialize or update knowledge about awailable ObjectTypes.

    :return:
    """

    assert glob.SCENE is None

    initialization = False

    # initialize with built-in types, this has to be done just once
    if not glob.OBJECT_TYPES:
        glob.logger.debug("Initialization of object types.")
        initialization = True
        await hlp.run_in_executor(prepare_object_types_dir, settings.OBJECT_TYPE_PATH, settings.OBJECT_TYPE_MODULE)
        glob.OBJECT_TYPES.update(built_in_types_data())

    updated_object_types: ObjectTypeDict = {}

    object_type_ids = {it.id for it in (await storage.get_object_type_ids()).items}

    for obj_id in object_type_ids:
        await get_object_data(updated_object_types, obj_id)

    removed_object_ids = {
        obj for obj in glob.OBJECT_TYPES.keys() if obj not in object_type_ids
    } - built_in_types_names()
    updated_object_ids = {k for k in updated_object_types.keys() if k in glob.OBJECT_TYPES}
    new_object_ids = {k for k in updated_object_types.keys() if k not in glob.OBJECT_TYPES}

    glob.logger.debug(f"Removed ids: {removed_object_ids}")
    glob.logger.debug(f"Updated ids: {updated_object_ids}")
    glob.logger.debug(f"New ids: {new_object_ids}")

    if not initialization and removed_object_ids:

        # TODO remove it from sys.modules

        remove_evt = ChangedObjectTypes([v.meta for k, v in glob.OBJECT_TYPES.items() if k in removed_object_ids])
        remove_evt.change_type = Event.Type.REMOVE
        asyncio.ensure_future(notif.broadcast_event(remove_evt))

        for removed in removed_object_ids:
            assert removed not in built_in_types_names(), "Attempt to remove built-in type."
            del glob.OBJECT_TYPES[removed]
            await hlp.run_in_executor(remove_object_type, removed)

    glob.OBJECT_TYPES.update(updated_object_types)

    glob.logger.debug(f"All known ids: {glob.OBJECT_TYPES.keys()}")

    for obj_type in updated_object_types.values():

        # if description is missing, try to get it from ancestor(s)
        if not obj_type.meta.description:

            try:
                obj_type.meta.description = obj_description_from_base(glob.OBJECT_TYPES, obj_type.meta)
            except otu.DataError as e:
                glob.logger.error(f"Failed to get info from base for {obj_type}, error: '{e}'.")

        if not obj_type.meta.disabled and not obj_type.meta.built_in:
            add_ancestor_actions(obj_type.meta.type, glob.OBJECT_TYPES)

    if not initialization:

        if updated_object_ids:
            update_evt = ChangedObjectTypes([v.meta for k, v in glob.OBJECT_TYPES.items() if k in updated_object_ids])
            update_evt.change_type = Event.Type.UPDATE
            asyncio.ensure_future(notif.broadcast_event(update_evt))

        if new_object_ids:
            add_evt = ChangedObjectTypes([v.meta for k, v in glob.OBJECT_TYPES.items() if k in new_object_ids])
            add_evt.change_type = Event.Type.ADD
            asyncio.ensure_future(notif.broadcast_event(add_evt))

    for obj_type in updated_object_types.values():

        if obj_type.type_def and issubclass(obj_type.type_def, Robot) and not obj_type.type_def.abstract():
            await get_robot_meta(obj_type)
            asyncio.ensure_future(handle_robot_urdf(obj_type.type_def))

    # if object does not change but its base has changed, it has to be reloaded
    for obj_id, obj in glob.OBJECT_TYPES.items():

        if obj_id in updated_object_ids:
            continue

        if obj.type_def and obj.meta.base in updated_object_ids:

            glob.logger.debug(f"Re-importing {obj.meta.type} because its base {obj.meta.base} type has changed.")
            obj.type_def = await hlp.run_in_executor(
                hlp.import_type_def,
                obj.meta.type,
                Generic,
                settings.OBJECT_TYPE_PATH,
                settings.OBJECT_TYPE_MODULE,
            )


async def get_robot_instance(robot_id: str, end_effector_id: Optional[str] = None) -> Robot:

    if robot_id not in glob.SCENE_OBJECT_INSTANCES:
        raise Arcor2Exception("Robot not found.")

    robot_inst = glob.SCENE_OBJECT_INSTANCES[robot_id]
    if not isinstance(robot_inst, Robot):
        raise Arcor2Exception("Not a robot.")
    if end_effector_id and end_effector_id not in await hlp.run_in_executor(robot_inst.get_end_effectors_ids):
        raise Arcor2Exception("Unknown end effector ID.")
    return robot_inst
