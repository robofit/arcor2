#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import asyncio
import shutil
from typing import Optional, Type

import horast

from arcor2 import helpers as hlp
from arcor2.action import patch_object_actions
from arcor2.clients import aio_persistent_storage as storage
from arcor2.data.object_type import ObjectModel, ObjectTypeMeta
from arcor2.exceptions import Arcor2Exception
from arcor2.object_types import utils as otu
from arcor2.object_types.abstract import Generic, Robot
from arcor2.parameter_plugins import TYPE_TO_PLUGIN
from arcor2.server import globals as glob, settings
from arcor2.server.robot import get_robot_meta
from arcor2.source.object_types import prepare_object_types_dir


def get_obj_type_name(object_id: str) -> str:

    try:
        return glob.SCENE_OBJECT_INSTANCES[object_id].__class__.__name__
    except KeyError:
        raise Arcor2Exception("Unknown object id.")


def valid_object_types() -> otu.ObjectTypeDict:
    """
    To get only valid (not disabled) types.
    :return:
    """

    return {obj_type: obj for obj_type, obj in glob.OBJECT_TYPES.items() if not obj.meta.disabled}


def handle_robot_urdf(robot: Type[Robot]) -> None:

    if not robot.urdf_package_path:
        return

    shutil.copy(robot.urdf_package_path, settings.URDF_PATH)


async def get_object_data(object_types: otu.ObjectTypeDict, obj_id: str) -> None:

    if obj_id in object_types:
        return

    obj = await storage.get_object_type(obj_id)
    base = otu.base_from_source(obj.source, obj_id)
    if base and base not in object_types.keys():
        try:
            await get_object_data(object_types, base)
        except Arcor2Exception:
            object_types[obj_id] = \
                otu.ObjectTypeData(
                    ObjectTypeMeta(obj_id, "Object type disabled.", disabled=True, problem="Can't get base."))
            return

    try:
        type_def = await hlp.run_in_executor(
            hlp.save_and_import_type_def, obj.source, obj.id, Generic, settings.OBJECT_TYPE_PATH,
            settings.OBJECT_TYPE_MODULE)
        assert issubclass(type_def, Generic)
        meta = otu.meta_from_def(type_def)
    except Arcor2Exception as e:
        glob.logger.warning(f"Disabling object type {obj.id}.")
        glob.logger.debug(e, exc_info=True)
        object_types[obj_id] = \
            otu.ObjectTypeData(ObjectTypeMeta(obj_id, "Object type disabled.", disabled=True, problem=e.message))
        return

    patch_object_actions(type_def)

    if obj.model:
        model = await storage.get_model(obj.model.id, obj.model.type)
        kwargs = {model.type().value.lower(): model}
        meta.object_model = ObjectModel(model.type(), **kwargs)  # type: ignore

    ast = horast.parse(obj.source)
    otd = otu.ObjectTypeData(meta, type_def, otu.object_actions(TYPE_TO_PLUGIN, type_def, ast), ast)

    if issubclass(type_def, Robot):
        await get_robot_meta(otd)
        asyncio.ensure_future(hlp.run_in_executor(handle_robot_urdf, type_def))

    object_types[obj_id] = otd


async def get_object_types() -> None:

    await hlp.run_in_executor(prepare_object_types_dir, settings.OBJECT_TYPE_PATH, settings.OBJECT_TYPE_MODULE)

    object_types: otu.ObjectTypeDict = otu.built_in_types_data(TYPE_TO_PLUGIN)

    obj_ids = await storage.get_object_type_ids()

    for id_desc in obj_ids.items:
        await get_object_data(object_types, id_desc.id)

    for obj_type in object_types.values():

        # if description is missing, try to get it from ancestor(s)
        if not obj_type.meta.description:

            try:
                obj_type.meta.description = otu.obj_description_from_base(object_types, obj_type.meta)
            except otu.DataError as e:
                glob.logger.error(f"Failed to get info from base for {obj_type}, error: '{e}'.")

        if not obj_type.meta.disabled and not obj_type.meta.built_in:
            otu.add_ancestor_actions(obj_type.meta.type, object_types)

    glob.OBJECT_TYPES = object_types


async def get_robot_instance(robot_id: str, end_effector_id: Optional[str] = None) -> Robot:

    if robot_id not in glob.SCENE_OBJECT_INSTANCES:
        raise Arcor2Exception("Robot not found.")

    robot_inst = glob.SCENE_OBJECT_INSTANCES[robot_id]
    if not isinstance(robot_inst, Robot):
        raise Arcor2Exception("Not a robot.")
    if end_effector_id and end_effector_id not in await hlp.run_in_executor(robot_inst.get_end_effectors_ids):
        raise Arcor2Exception("Unknown end effector ID.")
    return robot_inst
