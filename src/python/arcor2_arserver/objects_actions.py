#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import asyncio
import os
from typing import Optional, Type

from arcor2 import helpers as hlp
from arcor2.action import patch_object_actions
from arcor2.clients import aio_persistent_storage as ps
from arcor2.data.object_type import ObjectModel
from arcor2.exceptions import Arcor2Exception
from arcor2.object_types import utils as otu
from arcor2.object_types.abstract import Generic, Robot
from arcor2.source.utils import parse
from arcor2_arserver import globals as glob
from arcor2_arserver import settings
from arcor2_arserver.clients import persistent_storage as storage
from arcor2_arserver.object_types.source import prepare_object_types_dir
from arcor2_arserver.object_types.utils import (
    ObjectTypeData,
    ObjectTypeDict,
    add_ancestor_actions,
    built_in_types_data,
    meta_from_def,
    obj_description_from_base,
    object_actions,
)
from arcor2_arserver.robot import get_robot_meta
from arcor2_arserver_data.objects import ObjectTypeMeta


def get_obj_type_name(object_id: str) -> str:

    assert glob.SCENE

    try:
        return glob.SCENE.object(object_id).type
    except KeyError:
        raise Arcor2Exception("Unknown object id.")


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

    if obj_id in object_types:
        return

    obj = await storage.get_object_type(obj_id)

    try:
        base = otu.base_from_source(obj.source, obj_id)
        if base and base not in object_types.keys():
            await get_object_data(object_types, base)
    except Arcor2Exception:
        object_types[obj_id] = ObjectTypeData(
            ObjectTypeMeta(obj_id, "Object type disabled.", disabled=True, problem="Can't get base.")
        )
        return

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

    patch_object_actions(type_def)

    if obj.model:
        model = await storage.get_model(obj.model.id, obj.model.type)
        kwargs = {model.type().value.lower(): model}
        meta.object_model = ObjectModel(model.type(), **kwargs)  # type: ignore

    ast = parse(obj.source)
    otd = ObjectTypeData(meta, type_def, object_actions(type_def, ast), ast)

    object_types[obj_id] = otd


async def get_object_types() -> None:

    await hlp.run_in_executor(prepare_object_types_dir, settings.OBJECT_TYPE_PATH, settings.OBJECT_TYPE_MODULE)

    object_types: ObjectTypeDict = built_in_types_data()

    obj_ids = await storage.get_object_type_ids()

    for id_desc in obj_ids.items:
        await get_object_data(object_types, id_desc.id)

    for obj_type in object_types.values():

        # if description is missing, try to get it from ancestor(s)
        if not obj_type.meta.description:

            try:
                obj_type.meta.description = obj_description_from_base(object_types, obj_type.meta)
            except otu.DataError as e:
                glob.logger.error(f"Failed to get info from base for {obj_type}, error: '{e}'.")

        if not obj_type.meta.disabled and not obj_type.meta.built_in:
            add_ancestor_actions(obj_type.meta.type, object_types)

    glob.OBJECT_TYPES = object_types

    for obj_type in glob.OBJECT_TYPES.values():

        if obj_type.type_def and issubclass(obj_type.type_def, Robot) and not obj_type.type_def.abstract():
            await get_robot_meta(obj_type)
            asyncio.ensure_future(handle_robot_urdf(obj_type.type_def))


async def get_robot_instance(robot_id: str, end_effector_id: Optional[str] = None) -> Robot:

    if robot_id not in glob.SCENE_OBJECT_INSTANCES:
        raise Arcor2Exception("Robot not found.")

    robot_inst = glob.SCENE_OBJECT_INSTANCES[robot_id]
    if not isinstance(robot_inst, Robot):
        raise Arcor2Exception("Not a robot.")
    if end_effector_id and end_effector_id not in await hlp.run_in_executor(robot_inst.get_end_effectors_ids):
        raise Arcor2Exception("Unknown end effector ID.")
    return robot_inst
