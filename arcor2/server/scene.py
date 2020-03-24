async def add_service_to_scene(srv: SceneService) -> Tuple[bool, str]:

    if srv.type not in SERVICE_TYPES:
        return False, "Unknown service type."

    if SERVICE_TYPES[srv.type].disabled:
        return False, "Service is disabled."

    if srv.type in SERVICES_INSTANCES:
        return False, "Service already in scene."

    srv_type = await storage.get_service_type(srv.type)
    cls_def = hlp.type_def_from_source(srv_type.source, srv_type.id, Service)

    if issubclass(cls_def, RobotService) and find_robot_service():
        return False, "Scene might contain only one robot service."

    try:
        srv_inst = await hlp.run_in_executor(cls_def, srv.configuration_id)
    except Arcor2Exception as e:
        await logger.error(e)
        return False, "System error"

    SERVICES_INSTANCES[srv.type] = srv_inst

    if isinstance(srv_inst, RobotService):
        await logger.info("RobotService added, adding collision models to all objects.")
        for obj_inst in SCENE_OBJECT_INSTANCES.values():
            await collision(obj_inst, srv_inst, add=True)

    return True, "ok"


async def add_object_to_scene(obj: SceneObject, add_to_scene=True, srv_obj_ok=False) -> Tuple[bool, str]:
    """

    :param obj:
    :param add_to_scene: Set to false to only create object instance and add its collision model (if any).
    :return:
    """

    assert SCENE

    if obj.type not in OBJECT_TYPES:
        # TODO try to get it from storage
        return False, "Unknown object type."

    obj_meta = OBJECT_TYPES[obj.type]

    if obj_meta.disabled:
        return False, "Object type disabled."

    if srv_obj_ok:  # just for internal usage

        if not obj_meta.needs_services <= valid_service_types().keys():
            return False, "Some of required services is not available."

        if not obj_meta.needs_services <= SERVICES_INSTANCES.keys():
            return False, "Some of required services is not in the scene."

    elif obj_meta.needs_services:
        return False, "Service(s)-based object."

    if obj_meta.abstract:
        return False, "Cannot instantiate abstract type."

    if obj.id in SCENE_OBJECT_INSTANCES or obj.id in SERVICES_INSTANCES:
        return False, "Object/service with that id already exists."

    if not hlp.is_valid_identifier(obj.id):
        return False, "Object ID invalid (should be snake_case)."

    await logger.debug(f"Creating instance {obj.id} ({obj.type}).")

    try:

        if obj.type in otu.built_in_types_names():
            cls = otu.get_built_in_type(obj.type)
        else:
            obj_type = await storage.get_object_type(obj.type)
            cls = hlp.type_def_from_source(obj_type.source, obj_type.id, Generic)

        coll_model: Optional[Models] = None
        if obj_meta.object_model:
            coll_model = obj_meta.object_model.model()

        if not obj_meta.needs_services:
            obj_inst = cls(obj.id, obj.pose, coll_model)
        else:

            srv_args: List[Service] = []

            for name, ttype in get_type_hints(cls.__init__).items():

                # service arguments should be listed first
                if not issubclass(ttype, Service):
                    break

                try:
                    srv_args.append(SERVICES_INSTANCES[ttype.__name__])
                except KeyError:
                    return False, f"Object type {obj.type} has invalid typ annotation in the constructor, " \
                                  f"service {ttype.__name__} not available."

            try:
                obj_inst = cls(*srv_args, obj.id, obj.pose, coll_model)  # type: ignore
            except TypeError as e:
                return False, f"System error ({e})."

        SCENE_OBJECT_INSTANCES[obj.id] = obj_inst

        if add_to_scene:
            SCENE.objects.append(obj)

        await collision(obj_inst, add=True)

    except Arcor2Exception as e:
        await logger.error(e)
        return False, "System error"

    return True, "ok"


async def auto_add_object_to_scene(obj_type_name: str) -> Tuple[bool, str]:

    assert SCENE

    if obj_type_name not in OBJECT_TYPES:
        return False, "Unknown object type."

    if obj_type_name in otu.built_in_types_names():
        return False, "Does not work for built in types."

    obj_meta = OBJECT_TYPES[obj_type_name]

    if not obj_meta.needs_services:
        return False, "Ordinary object."

    if obj_meta.abstract:
        return False, "Cannot instantiate abstract type."

    if not obj_meta.needs_services <= valid_service_types().keys():
        return False, "Some of required services is not available."

    if not obj_meta.needs_services <= SERVICES_INSTANCES.keys():
        return False, "Some of required services is not in the scene."

    try:

        obj_type = await storage.get_object_type(obj_type_name)
        cls = hlp.type_def_from_source(obj_type.source, obj_type.id, Generic)

        args: List[Service] = [SERVICES_INSTANCES[srv_name] for srv_name in obj_meta.needs_services]

        assert hasattr(cls, otu.SERVICES_METHOD_NAME)
        for obj_inst in cls.from_services(*args):  # type: ignore

            assert isinstance(obj_inst, Generic)

            if not hlp.is_valid_identifier(obj_inst.id):
                # TODO add message to response
                await logger.warning(f"Object id {obj_inst.id} invalid.")
                continue

            if obj_inst.id in SCENE_OBJECT_INSTANCES:
                await logger.warning(f"Object id {obj_inst.id} already in scene.")
                continue

            SCENE_OBJECT_INSTANCES[obj_inst.id] = obj_inst
            SCENE.objects.append(obj_inst.scene_object())

            if obj_meta.object_model:
                obj_inst.collision_model = obj_meta.object_model.model()
                await collision(obj_inst, add=True)

    except Arcor2Exception as e:
        await logger.error(e)
        return False, "System error"

    return True, "ok"


async def clear_scene():

    rs = find_robot_service()
    if rs:
        for obj_inst in SCENE_OBJECT_INSTANCES.values():
            await collision(obj_inst, rs, remove=True)
    SCENE_OBJECT_INSTANCES.clear()
    SERVICES_INSTANCES.clear()


async def open_scene(scene_id: str):

    global SCENE
    SCENE = await storage.get_scene(scene_id)

    for srv in SCENE.services:
        res, msg = await add_service_to_scene(srv)
        if not res:
            raise Arcor2Exception(msg)

    for obj in SCENE.objects:
        res, msg = await add_object_to_scene(obj, add_to_scene=False, srv_obj_ok=True)
        if not res:
            raise Arcor2Exception(msg)

    assert {srv.type for srv in SCENE.services} == SERVICES_INSTANCES.keys()
    assert {obj.id for obj in SCENE.objects} == SCENE_OBJECT_INSTANCES.keys()

    asyncio.ensure_future(notify_scene_change_to_others())