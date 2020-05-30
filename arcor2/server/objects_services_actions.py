#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from typing import Callable, Any, Union, Dict, Optional, Type
import asyncio
import shutil

from arcor2 import service_types_utils as stu, object_types_utils as otu
from arcor2.data.object_type import ObjectModel, ObjectTypeMeta, ObjectTypeMetaDict, ObjectActionsDict
from arcor2.data.services import ServiceTypeMeta, ServiceTypeMetaDict
from arcor2 import aio_persistent_storage as storage
from arcor2.object_types import Robot
from arcor2.exceptions import Arcor2Exception
from arcor2.services import RobotService, Service
from arcor2.object_types import Generic
from arcor2.parameter_plugins import TYPE_TO_PLUGIN
import arcor2.helpers as hlp
from arcor2.data import events

from arcor2.server import globals as glob, settings
from arcor2.server.robot import get_robot_meta
from arcor2.server import notifications as notif


def find_robot_service() -> Union[None, RobotService]:

    for srv in glob.SERVICES_INSTANCES.values():
        if isinstance(srv, RobotService):
            return srv
    else:
        return None


def get_obj_type_name(object_id: str) -> str:

    return glob.SCENE_OBJECT_INSTANCES[object_id].__class__.__name__


def valid_object_types() -> ObjectTypeMetaDict:
    """
    To get only valid (not disabled) types.
    :return:
    """

    return {obj_type: obj for obj_type, obj in glob.OBJECT_TYPES.items() if not obj.disabled}


def valid_service_types() -> ServiceTypeMetaDict:
    """
    To get only valid (not disabled) types.
    :return:
    """

    return {srv_type: srv for srv_type, srv in glob.SERVICE_TYPES.items() if not srv.disabled}


async def get_service_types() -> None:

    service_types: ServiceTypeMetaDict = {}

    srv_ids = await storage.get_service_type_ids()

    # TODO do it in parallel
    for srv_id in srv_ids.items:

        srv_type = await storage.get_service_type(srv_id.id)

        try:
            type_def = hlp.type_def_from_source(srv_type.source, srv_type.id, Service)
            meta = stu.meta_from_def(type_def)
            service_types[srv_id.id] = meta
        except Arcor2Exception as e:
            await glob.logger.warning(f"Disabling service type {srv_type.id}.")
            await glob.logger.debug(e, exc_info=True)
            service_types[srv_id.id] = ServiceTypeMeta(srv_id.id, "Service not available.", disabled=True,
                                                       problem=e.message)
            continue

        if not meta.configuration_ids:
            meta.disabled = True
            meta.problem = "No configuration available."
            continue

        glob.TYPE_DEF_DICT[srv_id.id] = type_def

        if issubclass(type_def, RobotService):
            asyncio.ensure_future(get_robot_meta(type_def))

    glob.SERVICE_TYPES = service_types


def handle_robot_urdf(robot: Type[Robot]) -> None:

    if not robot.urdf_package_path:
        return

    shutil.copy(robot.urdf_package_path, settings.URDF_PATH)


async def get_object_types() -> None:

    object_types: ObjectTypeMetaDict = otu.built_in_types_meta()

    obj_ids = await storage.get_object_type_ids()

    # TODO do it in parallel
    for obj_id in obj_ids.items:
        obj = await storage.get_object_type(obj_id.id)
        try:
            type_def = hlp.type_def_from_source(obj.source, obj.id, Generic)
            meta = otu.meta_from_def(type_def)
            object_types[obj.id] = meta
        except (otu.ObjectTypeException, hlp.TypeDefException) as e:
            await glob.logger.warning(f"Disabling object type {obj.id}.")
            await glob.logger.debug(e, exc_info=True)
            object_types[obj.id] = ObjectTypeMeta(obj_id.id, "Object type disabled.", disabled=True,
                                                  problem=e.message)
            continue

        for srv in meta.needs_services:
            try:
                if glob.SERVICE_TYPES[srv].disabled:
                    meta.disabled = True
                    meta.problem = f"Depends on disabled service '{srv}'."
                    break
            except KeyError:
                meta.disabled = True
                meta.problem = f"Depends on unknown service '{srv}'."
                break

        glob.TYPE_DEF_DICT[obj.id] = type_def

        if obj.model:
            model = await storage.get_model(obj.model.id, obj.model.type)
            kwargs = {model.type().value.lower(): model}
            object_types[obj.id].object_model = ObjectModel(model.type(), **kwargs)  # type: ignore

        if issubclass(type_def, Robot):
            asyncio.ensure_future(get_robot_meta(type_def))
            asyncio.ensure_future(hlp.run_in_executor(handle_robot_urdf, type_def))

    # if description is missing, try to get it from ancestor(s)
    for obj_type, obj_meta in object_types.items():
        if obj_meta.description:
            continue

        try:
            obj_meta.description = otu.obj_description_from_base(object_types, obj_meta)
        except otu.DataError as e:
            await glob.logger.error(f"Failed to get info from base for {obj_type}, error: '{e}'.")

    glob.OBJECT_TYPES = object_types


async def get_object_actions() -> None:  # TODO do it in parallel

    global ACTIONS

    object_actions_dict: ObjectActionsDict = otu.built_in_types_actions(TYPE_TO_PLUGIN)

    valid_types = valid_object_types()

    for obj_type, obj in valid_types.items():

        if obj.built_in:  # built-in types are already there
            continue

        # db-stored (user-created) object types
        obj_db = await storage.get_object_type(obj_type)
        try:
            type_def = hlp.type_def_from_source(obj_db.source, obj_db.id, Generic)
            object_actions_dict[obj_type] = otu.object_actions(TYPE_TO_PLUGIN, type_def, obj_db.source)
        except hlp.TypeDefException as e:
            await glob.logger.error(e)

    # add actions from ancestors
    for obj_type in valid_types.keys():
        otu.add_ancestor_actions(obj_type, object_actions_dict, glob.OBJECT_TYPES)

    # get services' actions
    for service_type, service_meta in valid_service_types().items():

        if service_meta.built_in:
            continue

        srv_type = await storage.get_service_type(service_type)
        try:
            srv_type_def = hlp.type_def_from_source(srv_type.source, service_type, Service)
            object_actions_dict[service_type] = otu.object_actions(TYPE_TO_PLUGIN, srv_type_def, srv_type.source)
        except Arcor2Exception:
            await glob.logger.exception(f"Error while processing service type {service_type}")

    glob.ACTIONS = object_actions_dict

    await notif.broadcast_event(events.ObjectTypesChangedEvent(data=list(object_actions_dict.keys())))


async def get_robot_instance(robot_id: str, end_effector_id: Optional[str] = None) -> Union[Robot, RobotService]:

    if robot_id in glob.SCENE_OBJECT_INSTANCES:
        robot_inst = glob.SCENE_OBJECT_INSTANCES[robot_id]
        if not isinstance(robot_inst, Robot):
            raise Arcor2Exception("Not a robot.")
        if end_effector_id and end_effector_id not in await hlp.run_in_executor(robot_inst.get_end_effectors_ids):
            raise Arcor2Exception("Unknown end effector ID.")
        return robot_inst
    else:
        robot_srv_inst = find_robot_service()
        if not robot_srv_inst or robot_id not in await hlp.run_in_executor(robot_srv_inst.get_robot_ids):
            raise Arcor2Exception("Unknown robot ID.")
        if end_effector_id and end_effector_id not in await hlp.run_in_executor(robot_srv_inst.get_end_effectors_ids,
                                                                                robot_id):
            raise Arcor2Exception("Unknown end effector ID.")
        return robot_srv_inst


async def execute_action(action_method: Callable, params: Dict[str, Any]) -> None:

    assert glob.RUNNING_ACTION

    await notif.broadcast_event(events.ActionExecutionEvent(data=events.ActionExecutionData(glob.RUNNING_ACTION)))

    evt = events.ActionResultEvent()
    evt.data.action_id = glob.RUNNING_ACTION

    try:
        action_result = await hlp.run_in_executor(action_method, *params.values())
    except Arcor2Exception as e:
        await glob.logger.error(e)
        evt.data.error = e.message
    except (AttributeError, TypeError) as e:
        await glob.logger.error(e)
        evt.data.error = str(e)
    else:
        if action_result is not None:
            try:
                evt.data.result = TYPE_TO_PLUGIN[type(action_result)].value_to_json(action_result)
            except KeyError:
                # temporal workaround for unsupported types
                evt.data.result = str(action_result)

    if glob.RUNNING_ACTION is None:
        # action was cancelled, do not send any event
        return

    await notif.broadcast_event(evt)
    glob.RUNNING_ACTION = None
    glob.RUNNING_ACTION_PARAMS = None
