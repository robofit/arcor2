import asyncio
from typing import NamedTuple

from arcor2 import helpers as hlp
from arcor2.cached import CachedScene
from arcor2.clients import aio_asset as asset
from arcor2.data.events import Event
from arcor2.data.object_type import Mesh, ObjectModel
from arcor2.exceptions import Arcor2Exception
from arcor2.object_types import utils as otu
from arcor2.object_types.abstract import Generic, Robot
from arcor2.object_types.utils import built_in_types_names, prepare_object_types_dir
from arcor2.parameter_plugins.base import TypesDict
from arcor2.source.utils import parse
from arcor2_arserver import globals as glob
from arcor2_arserver import logger
from arcor2_arserver import notifications as notif
from arcor2_arserver import settings
from arcor2_arserver.clients import project_service as storage
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


def get_obj_type_data(scene: CachedScene, object_id: str) -> ObjectTypeData:
    return glob.OBJECT_TYPES[scene.object(object_id).type]


def valid_object_types() -> ObjectTypeDict:
    """To get only valid (not disabled) types.

    :return:
    """

    return {obj_type: obj for obj_type, obj in glob.OBJECT_TYPES.items() if not obj.meta.disabled}


async def get_object_data(object_types: ObjectTypeDict, obj_id: str) -> None:

    logger.debug(f"Processing {obj_id}.")

    if obj_id in object_types:
        logger.debug(f"{obj_id} already processed, skipping...")
        return

    obj_iddesc = await storage.get_object_type_iddesc(obj_id)

    if obj_id in glob.OBJECT_TYPES:

        assert obj_iddesc.modified
        assert glob.OBJECT_TYPES[obj_id].meta.modified, f"Object {obj_id} does not have 'modified' in its meta."

        if obj_iddesc.modified == glob.OBJECT_TYPES[obj_id].meta.modified:
            logger.debug(f"No need to update {obj_id}.")
            return

    obj = await storage.get_object_type(obj_id)

    try:
        bases = otu.base_from_source(obj.source, obj_id)

        if not bases:
            logger.debug(f"{obj_id} is definitely not an ObjectType (subclass of {object.__name__}), maybe mixin?")
            return

        if bases[0] not in object_types.keys() | built_in_types_names():
            logger.debug(f"Getting base class {bases[0]} for {obj_id}.")
            await get_object_data(object_types, bases[0])

        for mixin in bases[1:]:
            mixin_obj = await storage.get_object_type(mixin)

            await hlp.run_in_executor(
                hlp.save_and_import_type_def,
                mixin_obj.source,
                mixin_obj.id,
                object,
                settings.OBJECT_TYPE_PATH,
                settings.OBJECT_TYPE_MODULE,
            )

    except Arcor2Exception as e:
        logger.error(f"Disabling ObjectType {obj.id}: can't get a base. {str(e)}")
        object_types[obj_id] = ObjectTypeData(
            ObjectTypeMeta(
                obj_id, "ObjectType disabled.", disabled=True, problem="Can't get base.", modified=obj.modified
            )
        )
        return

    logger.debug(f"Updating {obj_id}.")

    try:
        type_def = await hlp.run_in_executor(
            hlp.save_and_import_type_def,
            obj.source,
            obj.id,
            Generic,
            settings.OBJECT_TYPE_PATH,
            settings.OBJECT_TYPE_MODULE,
        )
    except Arcor2Exception as e:
        logger.debug(f"{obj.id} is probably not an ObjectType. {str(e)}")
        return

    assert issubclass(type_def, Generic)

    try:
        meta = meta_from_def(type_def)
    except Arcor2Exception as e:
        logger.error(f"Disabling ObjectType {obj.id}.")
        logger.debug(e, exc_info=True)
        object_types[obj_id] = ObjectTypeData(
            ObjectTypeMeta(obj_id, "ObjectType disabled.", disabled=True, problem=str(e), modified=obj.modified)
        )
        return

    meta.modified = obj.modified

    if obj.model:
        try:
            model = await storage.get_model(obj.model.id, obj.model.type)
        except Arcor2Exception as e:
            logger.error(f"{obj.model.id}: failed to get collision model of type {obj.model.type}. {str(e)}")
            meta.disabled = True
            meta.problem = "Can't get collision model."
            object_types[obj_id] = ObjectTypeData(meta)
            return

        if isinstance(model, Mesh) and not await asset.asset_exists(model.asset_id):
            logger.error(f"Disabling {meta.type} as its mesh file {model.asset_id} does not exist.")
            meta.disabled = True
            meta.problem = "Mesh file does not exist."
            object_types[obj_id] = ObjectTypeData(meta)
            return

        kwargs = {model.type().value.lower(): model}
        meta.object_model = ObjectModel(model.type(), **kwargs)  # type: ignore

    ast = parse(obj.source)
    otd = ObjectTypeData(meta, type_def, object_actions(type_def, ast), ast)

    object_types[obj_id] = otd


class UpdatedObjectTypes(NamedTuple):

    new: set[str]
    updated: set[str]
    removed: set[str]

    @property
    def all(self) -> set[str]:
        return self.new | self.updated | self.removed


async def get_object_types() -> UpdatedObjectTypes:
    """Serves to initialize or update knowledge about awailable ObjectTypes.

    :return:
    """

    initialization = False

    # initialize with built-in types, this has to be done just once
    if not glob.OBJECT_TYPES:
        logger.debug("Initialization of ObjectTypes.")
        initialization = True
        await hlp.run_in_executor(prepare_object_types_dir, settings.OBJECT_TYPE_PATH, settings.OBJECT_TYPE_MODULE)
        glob.OBJECT_TYPES.update(built_in_types_data())

    updated_object_types: ObjectTypeDict = {}

    object_type_ids: set[str] | list[str] = await storage.get_object_type_ids()

    if __debug__:  # this should uncover potential problems with order in which ObjectTypes are processed
        import random

        object_type_ids = list(object_type_ids)
        random.shuffle(object_type_ids)

    for obj_id in object_type_ids:
        await get_object_data(updated_object_types, obj_id)

    removed_object_ids = {
        obj for obj in glob.OBJECT_TYPES.keys() if obj not in object_type_ids
    } - built_in_types_names()
    updated_object_ids = {k for k in updated_object_types.keys() if k in glob.OBJECT_TYPES}
    new_object_ids = {k for k in updated_object_types.keys() if k not in glob.OBJECT_TYPES}

    logger.debug(f"Removed ids: {removed_object_ids}")
    logger.debug(f"Updated ids: {updated_object_ids}")
    logger.debug(f"New ids: {new_object_ids}")

    if not initialization and removed_object_ids:

        # TODO remove it from sys.modules

        remove_evt = ChangedObjectTypes([v.meta for k, v in glob.OBJECT_TYPES.items() if k in removed_object_ids])
        remove_evt.change_type = Event.Type.REMOVE
        asyncio.ensure_future(notif.broadcast_event(remove_evt))

        for removed in removed_object_ids:
            assert removed not in built_in_types_names(), "Attempt to remove built-in type."
            del glob.OBJECT_TYPES[removed]
            await remove_object_type(removed)

    glob.OBJECT_TYPES.update(updated_object_types)

    logger.debug(f"All known ids: {glob.OBJECT_TYPES.keys()}")

    for obj_type in updated_object_types.values():

        # if description is missing, try to get it from ancestor(s)
        if not obj_type.meta.description:

            try:
                obj_type.meta.description = obj_description_from_base(glob.OBJECT_TYPES, obj_type.meta)
            except otu.DataError as e:
                logger.error(f"Failed to get info from base for {obj_type}, error: '{e}'.")

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

    # if object does not change but its base has changed, it has to be reloaded
    for obj_id, obj in glob.OBJECT_TYPES.items():

        if obj_id in updated_object_ids:
            continue

        if obj.type_def and obj.meta.base in updated_object_ids:

            logger.debug(f"Re-importing {obj.meta.type} because its base {obj.meta.base} type has changed.")
            obj.type_def = await hlp.run_in_executor(
                hlp.import_type_def,
                obj.meta.type,
                Generic,
                settings.OBJECT_TYPE_PATH,
                settings.OBJECT_TYPE_MODULE,
            )

    return UpdatedObjectTypes(new_object_ids, updated_object_ids, removed_object_ids)


async def update_object_model(meta: ObjectTypeMeta, om: ObjectModel) -> None:

    if not meta.object_model:
        return

    model = om.model()

    if model.id != meta.type:
        raise Arcor2Exception("Model id must be equal to ObjectType id.")

    if isinstance(model, Mesh):
        if not await asset.asset_exists(model.asset_id):
            raise Arcor2Exception(f"File {model.asset_id} associated to mesh {model.id} does not exist.")

    # when updating model of an already existing object, the type might be different
    if meta.object_model.type != om.type:
        await storage.delete_model(model.id)  # ...otherwise it is going to be an orphan

    await storage.put_model(model)
