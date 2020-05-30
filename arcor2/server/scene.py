import asyncio
from typing import Optional, List, get_type_hints, Set, AsyncIterator, Union

from arcor2.data.common import SceneService, SceneObject, Scene
from arcor2.data import events
from arcor2.data.object_type import Models
from arcor2.exceptions import Arcor2Exception
from arcor2.services import Service, RobotService
from arcor2.object_types import Generic
from arcor2 import aio_persistent_storage as storage, helpers as hlp, object_types_utils as otu

from arcor2.server import globals as glob, notifications as notif, objects_services_actions as osa
from arcor2.server.robot import collision


def instances_names() -> Set[str]:
    return {obj.name for obj in glob.SCENE_OBJECT_INSTANCES.values()}


async def scenes() -> AsyncIterator[Scene]:

    for scene_id in (await storage.get_scenes()).items:
        yield await storage.get_scene(scene_id.id)


async def add_service_to_scene(srv: SceneService, dry_run: bool = False) -> None:

    if srv.type not in glob.SERVICE_TYPES:
        raise Arcor2Exception("Unknown service type.")

    if glob.SERVICE_TYPES[srv.type].disabled:
        raise Arcor2Exception("Service is disabled.")

    if srv.type in glob.SERVICES_INSTANCES:
        raise Arcor2Exception("Service already in scene.")

    if dry_run:
        return None

    srv_type = await storage.get_service_type(srv.type)
    cls_def = hlp.type_def_from_source(srv_type.source, srv_type.id, Service)

    if issubclass(cls_def, RobotService) and osa.find_robot_service():
        raise Arcor2Exception("Scene might contain only one robot service.")

    srv_inst = await hlp.run_in_executor(cls_def, srv.configuration_id)

    glob.SERVICES_INSTANCES[srv.type] = srv_inst

    if isinstance(srv_inst, RobotService):
        await glob.logger.info("RobotService added, adding collision models to all objects.")
        for obj_inst in glob.SCENE_OBJECT_INSTANCES.values():
            await collision(obj_inst, srv_inst, add=True)

    return None


async def add_object_to_scene(obj: SceneObject, add_to_scene=True, srv_obj_ok=False, dry_run: bool = False):
    """

    :param obj:
    :param add_to_scene: Set to false to only create object instance and add its collision model (if any).
    :return:
    """

    assert glob.SCENE

    if obj.type not in glob.OBJECT_TYPES:
        raise Arcor2Exception("Unknown object type.")

    obj_meta = glob.OBJECT_TYPES[obj.type]

    if obj_meta.disabled:
        raise Arcor2Exception("Object type disabled.")

    if srv_obj_ok:  # just for internal usage

        if not obj_meta.needs_services <= osa.valid_service_types().keys():
            raise Arcor2Exception("Some of required services is not available.")

        if not obj_meta.needs_services <= glob.SERVICES_INSTANCES.keys():
            raise Arcor2Exception("Some of required services is not in the scene.")

    elif obj_meta.needs_services:
        raise Arcor2Exception("Service(s)-based object.")

    if obj_meta.abstract:
        raise Arcor2Exception("Cannot instantiate abstract type.")

    if obj.id in glob.SCENE_OBJECT_INSTANCES or obj.id in glob.SERVICES_INSTANCES:
        raise Arcor2Exception("Object/service with that id already exists.")

    if obj.name in instances_names():
        raise Arcor2Exception("Name is already used.")

    if not hlp.is_valid_identifier(obj.name):
        raise Arcor2Exception("Object name invalid (should be snake_case).")

    if dry_run:
        return None

    await glob.logger.debug(f"Creating instance {obj.id} ({obj.type}).")

    if obj.type in otu.built_in_types_names():
        cls = otu.get_built_in_type(obj.type)
    else:
        obj_type = await storage.get_object_type(obj.type)
        cls = hlp.type_def_from_source(obj_type.source, obj_type.id, Generic)

    coll_model: Optional[Models] = None
    if obj_meta.object_model:
        coll_model = obj_meta.object_model.model()

    if not obj_meta.needs_services:
        obj_inst = cls(obj.id, obj.name, obj.pose, coll_model)
    else:

        srv_args: List[Service] = []

        for name, ttype in get_type_hints(cls.__init__).items():

            # service arguments should be listed first
            if not issubclass(ttype, Service):
                break

            try:
                srv_args.append(glob.SERVICES_INSTANCES[ttype.__name__])
            except KeyError:
                return False, f"Object type {obj.type} has invalid typ annotation in the constructor, " \
                              f"service {ttype.__name__} not available."

        try:
            obj_inst = cls(*srv_args, obj.id, obj.name, obj.pose, coll_model)  # type: ignore
        except TypeError as e:
            raise Arcor2Exception("System error.") from e

    glob.SCENE_OBJECT_INSTANCES[obj.id] = obj_inst

    if add_to_scene:
        glob.SCENE.objects.append(obj)

    await collision(obj_inst, add=True)

    return None


async def auto_add_object_to_scene(obj_type_name: str, dry_run: bool = False) -> None:

    assert glob.SCENE

    if obj_type_name not in glob.OBJECT_TYPES:
        raise Arcor2Exception("Unknown object type.")

    if obj_type_name in otu.built_in_types_names():
        raise Arcor2Exception("Does not work for built in types.")

    obj_meta = glob.OBJECT_TYPES[obj_type_name]

    if not obj_meta.needs_services:
        raise Arcor2Exception("Ordinary object.")

    if obj_meta.abstract:
        raise Arcor2Exception("Cannot instantiate abstract type.")

    if not obj_meta.needs_services <= osa.valid_service_types().keys():
        raise Arcor2Exception("Some of required services is not available.")

    if not obj_meta.needs_services <= glob.SERVICES_INSTANCES.keys():
        raise Arcor2Exception("Some of required services is not in the scene.")

    if dry_run:
        return None

    obj_type = await storage.get_object_type(obj_type_name)
    cls = hlp.type_def_from_source(obj_type.source, obj_type.id, Generic)

    args: List[Service] = [glob.SERVICES_INSTANCES[srv_name] for srv_name in obj_meta.needs_services]

    assert hasattr(cls, otu.SERVICES_METHOD_NAME)
    for obj_inst in cls.from_services(*args):  # type: ignore

        assert isinstance(obj_inst, Generic)

        if not hlp.is_valid_identifier(obj_inst.name):
            # TODO add message to response
            await glob.logger.warning(f"Object id {obj_inst.id} invalid.")
            continue

        if obj_inst.id in glob.SCENE_OBJECT_INSTANCES:
            await glob.logger.warning(f"Object id {obj_inst.id} already in scene.")
            continue

        if obj_inst.name in instances_names():
            await glob.logger.warning(f"Duplicate object name {obj_inst.name}.")
            continue

        glob.SCENE_OBJECT_INSTANCES[obj_inst.id] = obj_inst

        obj = obj_inst.scene_object()
        glob.SCENE.objects.append(obj)

        asyncio.ensure_future(notif.broadcast_event(events.SceneObjectChanged(events.EventType.ADD, data=obj)))

        if obj_meta.object_model:
            obj_inst.collision_model = obj_meta.object_model.model()
            await collision(obj_inst, add=True)

    return None


async def clear_scene() -> None:

    await glob.logger.info("Clearing the scene.")
    rs = osa.find_robot_service()
    if rs:
        for obj_inst in glob.SCENE_OBJECT_INSTANCES.values():
            await collision(obj_inst, rs, remove=True)
    glob.SCENE_OBJECT_INSTANCES.clear()
    glob.SERVICES_INSTANCES.clear()  # TODO call destroy

    glob.SCENE = None


async def open_scene(scene_id: str) -> None:

    glob.SCENE = await storage.get_scene(scene_id)

    try:

        for srv in glob.SCENE.services:
            await add_service_to_scene(srv)

        for obj in glob.SCENE.objects:
            await add_object_to_scene(obj, add_to_scene=False, srv_obj_ok=True)

    except Arcor2Exception as e:
        await clear_scene()
        raise Arcor2Exception(f"Failed to open scene. {e.message}") from e

    assert {srv.type for srv in glob.SCENE.services} == glob.SERVICES_INSTANCES.keys()
    assert {obj.id for obj in glob.SCENE.objects} == glob.SCENE_OBJECT_INSTANCES.keys()


def get_instance(obj_id: str) -> Union[Generic, Service]:

    if obj_id in glob.SCENE_OBJECT_INSTANCES:
        return glob.SCENE_OBJECT_INSTANCES[obj_id]
    elif obj_id in glob.SERVICES_INSTANCES:
        return glob.SERVICES_INSTANCES[obj_id]
    else:
        raise Arcor2Exception("Unknown object/service ID.")
