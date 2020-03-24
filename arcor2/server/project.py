

async def scene_object_pose_updated(scene_id: str, obj_id: str) -> None:

    async for project in projects_using_object(scene_id, obj_id):

        for obj in project.objects:
            if obj.id != obj_id:
                continue
            for ap in obj.action_points:
                for joints in ap.robot_joints:
                    joints.is_valid = False

        await storage.update_project(project)

async def remove_object_references_from_projects(obj_id: str) -> None:

    assert SCENE

    updated_project_ids: Set[str] = set()

    async for project in projects_using_object(SCENE.id, obj_id):

        # delete object and its action points
        project.objects = [obj for obj in project.objects if obj.id != obj_id]

        action_ids: Set[str] = set()

        for obj in project.objects:
            for ap in obj.action_points:

                # delete actions using the object
                ap.actions = [act for act in ap.actions if act.parse_type()[0] != obj_id]

                # delete actions using obj's action points as parameters
                # TODO fix this!
                """
                actions_using_invalid_param: Set[str] = \
                    {act.id for act in ap.actions for param in act.parameters
                     if param.type in (ActionParameterTypeEnum.JOINTS, ActionParameterTypeEnum.POSE) and
                     param.value.startswith(obj_id)}

                ap.actions = [act for act in ap.actions if act.id not in actions_using_invalid_param]

                # get IDs of remaining actions
                action_ids.update({act.id for act in ap.actions})
                """

        valid_ids: Set[str] = action_ids | ActionIOEnum.set()

        # remove invalid inputs/outputs
        for obj in project.objects:
            for ap in obj.action_points:
                for act in ap.actions:
                    act.inputs = [input for input in act.inputs if input.default in valid_ids]
                    act.outputs = [output for output in act.outputs if output.default in valid_ids]

        await storage.update_project(project)
        updated_project_ids.add(project.id)

    await logger.info("Updated projects: {}".format(updated_project_ids))


async def projects_using_object(scene_id: str, obj_id: str) -> AsyncIterator[Project]:

    id_list = await storage.get_projects()

    for project_meta in id_list.items:

        project = await storage.get_project(project_meta.id)

        if project.scene_id != scene_id:
            continue

        for obj in project.objects:

            if obj.id == obj_id:
                yield project
                break

            for ap in obj.action_points:
                for action in ap.actions:
                    action_obj_id, _ = action.parse_type()

                    if action_obj_id == obj_id:
                        yield project
                        break


def project_problems(scene: Scene, project: Project) -> List[str]:

    scene_objects: Dict[str, str] = {obj.id: obj.type for obj in scene.objects}
    scene_services: Set[str] = {srv.type for srv in scene.services}

    action_ids: Set[str] = set()
    problems: List[str] = []

    unknown_types = ({obj.type for obj in scene.objects} | scene_services) - ACTIONS.keys()

    if unknown_types:
        return [f"Scene invalid, contains unknown types: {unknown_types}."]

    for obj in project.objects:

        # test if all objects exists in scene
        if obj.id not in scene_objects:
            problems.append(f"Object ID {obj.id} does not exist in scene.")
            continue

        for ap in obj.action_points:

            for joints in ap.robot_joints:
                if not joints.is_valid:
                    problems.append(f"Action point {ap.id} has invalid joints: {joints.id} (robot {joints.robot_id}).")

            for action in ap.actions:

                if action.id in action_ids:
                    problems.append(f"Action ID {action.id} of the {obj.id}/{ap.id} is not unique.")

                # check if objects have used actions
                obj_id, action_type = action.parse_type()

                if obj_id not in scene_objects.keys() | scene_services:
                    problems.append(f"Object ID {obj.id} which action is used in {action.id} does not exist in scene.")
                    continue

                try:
                    os_type = scene_objects[obj_id]  # object type
                except KeyError:
                    os_type = obj_id  # service

                for act in ACTIONS[os_type]:
                    if action_type == act.name:
                        break
                else:
                    problems.append(f"Object type {scene_objects[obj_id]} does not have action {action_type} "
                                    f"used in {action.id}.")

                # check object's actions parameters
                action_params: Dict[str, str] = \
                    {param.id: param.type for param in action.parameters}
                ot_params: Dict[str, str] = {param.name: param.type for param in act.parameters
                                             for act in ACTIONS[os_type]}

                if action_params != ot_params:
                    problems.append(f"Action ID {action.id} of type {action.type} has invalid parameters.")

                # TODO validate parameter values / instances (for value) are not available here / how to solve it?
                for param in action.parameters:
                    try:
                        PARAM_PLUGINS[param.type].value(TYPE_DEF_DICT, scene, project, action.id, param.id)
                    except ParameterPluginException:
                        problems.append(f"Parameter {param.id} of action {act.name} "
                                        f"has invalid value: '{param.value}'.")

    return problems


async def open_project(project_id: str) -> None:

    global PROJECT

    PROJECT = await storage.get_project(project_id)
    res, msg = await open_scene(PROJECT.scene_id)
    if not res:
        raise Arcor2Exception(msg)

    assert SCENE
    for obj in PROJECT.objects:
        # TODO how to handle missing object?
        scene_obj = SCENE.object_or_service(obj.id)
        obj.uuid = scene_obj.uuid

    asyncio.ensure_future(notify_project_change_to_others())