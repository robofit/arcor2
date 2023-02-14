import asyncio
import copy
from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator

from websockets.server import WebSocketServerProtocol as WsClient

from arcor2 import helpers as hlp
from arcor2 import transformations as tr
from arcor2.cached import CachedProject, UpdateableCachedProject
from arcor2.data import common
from arcor2.data.events import Event, PackageState
from arcor2.exceptions import Arcor2Exception
from arcor2.logic import check_for_loops
from arcor2.object_types.abstract import Generic, Robot
from arcor2.parameter_plugins.base import ParameterPluginException
from arcor2.parameter_plugins.pose import PosePlugin
from arcor2.parameter_plugins.utils import plugin_from_type_name
from arcor2_arserver import globals as glob
from arcor2_arserver import logger
from arcor2_arserver import notifications as notif
from arcor2_arserver import project
from arcor2_arserver.checks import (
    check_action_params,
    check_ap_parent,
    check_flows,
    check_logic_item,
    check_project_parameter,
    find_object_action,
)
from arcor2_arserver.clients import project_service as storage
from arcor2_arserver.common import project_names, scene_names
from arcor2_arserver.helpers import (
    ctx_read_lock,
    ctx_write_lock,
    ensure_write_locked,
    get_unlocked_objects,
    make_name_unique,
    unique_name,
)
from arcor2_arserver.objects_actions import get_types_dict
from arcor2_arserver.project import close_project, get_project_problems, notify_project_opened, open_project
from arcor2_arserver.robot import check_eef_arm, get_end_effector_pose, get_pose_and_joints, get_robot_joints
from arcor2_arserver.scene import (
    can_modify_scene,
    ensure_scene_started,
    get_instance,
    get_robot_instance,
    open_scene,
    save_scene,
)
from arcor2_arserver_data import events as sevts
from arcor2_arserver_data import rpc as srpc


@asynccontextmanager
async def managed_project(project_id: str, make_copy: bool = False) -> AsyncGenerator[UpdateableCachedProject, None]:

    save_back = False

    if glob.LOCK.project and glob.LOCK.project.id == project_id:
        if make_copy:
            project = copy.deepcopy(glob.LOCK.project)
            save_back = True
        else:
            project = glob.LOCK.project
    else:
        save_back = True
        project = UpdateableCachedProject(await storage.get_project(project_id))

    if make_copy:
        project.id = common.Project.uid()

    try:
        yield project
    finally:
        if save_back:
            asyncio.ensure_future(storage.update_project(project))


async def cancel_action_cb(req: srpc.p.CancelAction.Request, ui: WsClient) -> None:

    scene = glob.LOCK.scene_or_exception()
    proj = glob.LOCK.project_or_exception()

    if not glob.RUNNING_ACTION:
        raise Arcor2Exception("No action is running.")

    action = proj.action(glob.RUNNING_ACTION)
    obj_id, action_name = action.parse_type()
    obj = get_instance(obj_id, Generic)

    if not find_object_action(glob.OBJECT_TYPES, scene, action).meta.cancellable:
        raise Arcor2Exception("Action is not cancellable.")

    try:
        action_method = getattr(obj, action_name)
        cancel_method = getattr(obj, obj.CANCEL_MAPPING[action_method.__name__])
    except AttributeError as e:
        raise Arcor2Exception("Internal error.") from e

    cancel_params: dict[str, Any] = {}

    # TODO fix or remove this?
    """
    cancel_sig = inspect.signature(cancel_method)

    assert glob.RUNNING_ACTION_PARAMS is not None

    for param_name in cancel_sig.parameters.keys():
        try:
            cancel_params[param_name] = glob.RUNNING_ACTION_PARAMS[param_name]
        except KeyError as e:
            raise Arcor2Exception("Cancel method parameters should be subset of action parameters.") from e
    """

    await hlp.run_in_executor(cancel_method, *cancel_params.values())

    asyncio.ensure_future(notif.broadcast_event(sevts.a.ActionCancelled()))
    glob.RUNNING_ACTION = None
    glob.RUNNING_ACTION_PARAMS = None


async def execute_action_cb(req: srpc.p.ExecuteAction.Request, ui: WsClient) -> None:

    scene = glob.LOCK.scene_or_exception()
    proj = glob.LOCK.project_or_exception()

    # TODO rather lock the project and release the lock once execution is finished?
    async with ctx_write_lock(glob.LOCK.SpecialValues.RUNNING_ACTION, glob.USERS.user_name(ui)):

        ensure_scene_started()

        if glob.RUNNING_ACTION:
            raise Arcor2Exception(
                f"Action {glob.RUNNING_ACTION} is being executed. " f"Only one action can be executed at a time."
            )

        action = proj.action(req.args.action_id)

        obj_id, action_name = action.parse_type()

        params: list[Any] = []

        for param in action.parameters:

            if param.type == common.ActionParameter.TypeEnum.LINK:

                parsed_link = param.parse_link()
                try:
                    results = glob.PREV_RESULTS[parsed_link.action_id]
                except KeyError:
                    prev_action = proj.action(parsed_link.action_id)
                    raise Arcor2Exception(f"Action '{prev_action.name}' has to be executed first.")

                # an action result could be a tuple or a single value
                if isinstance(results, tuple):
                    params.append(results[parsed_link.output_index])
                else:
                    assert parsed_link.output_index == 0
                    params.append(results)

            elif param.type == common.ActionParameter.TypeEnum.PROJECT_PARAMETER:
                pparam = proj.parameter(param.str_from_value())
                # TODO use plugin to get the value
                from arcor2 import json

                params.append(json.loads(pparam.value))
            else:

                try:
                    params.append(
                        plugin_from_type_name(param.type).parameter_execution_value(
                            get_types_dict(), scene, proj, action.id, param.name
                        )
                    )
                except ParameterPluginException as e:
                    logger.error(e)
                    raise Arcor2Exception(f"Failed to get value for parameter {param.name}.")

        obj = get_instance(obj_id, Generic)

        if isinstance(obj, Robot):
            if obj.move_in_progress:
                raise Arcor2Exception("Can't execute actions while the robot moves.")

        if not hasattr(obj, action_name):
            raise Arcor2Exception("Internal error: object does not have the requested method.")

        if req.dry_run:
            return

        glob.RUNNING_ACTION = action.id
        glob.RUNNING_ACTION_PARAMS = params

        logger.debug(f"Running action {action.name} ({type(obj)}/{action_name}), params: {params}.")

        # schedule execution and return success
        asyncio.ensure_future(project.execute_action(getattr(obj, action_name), params))
        return None


async def list_projects_cb(req: srpc.p.ListProjects.Request, ui: WsClient) -> srpc.p.ListProjects.Response:
    async def project_info(project_id: str) -> srpc.p.ListProjects.Response.Data:

        project = await storage.get_project(project_id)

        assert project.created
        assert project.modified

        pd = srpc.p.ListProjects.Response.Data(
            project.name,
            project.scene_id,
            project.description,
            project.has_logic,
            project.created,
            project.modified,
            id=project.id,
        )

        try:
            scene = await storage.get_scene(project.scene_id)
        except storage.ProjectServiceException:
            pd.problems = ["Scene does not exist."]
            return pd

        pd.problems = await get_project_problems(scene, project)
        return pd

    resp = srpc.p.ListProjects.Response()

    resp.data = []
    for res in await asyncio.gather(
        *[project_info(proj_id) for proj_id in (await storage.get_project_ids())], return_exceptions=True
    ):

        if isinstance(res, Arcor2Exception):
            logger.error(str(res))
        elif isinstance(res, Exception):
            raise res  # zero toleration for other exceptions
        else:
            resp.data.append(res)

    return resp


async def get_project_cb(req: srpc.p.GetProject.Request, ui: WsClient) -> srpc.p.GetProject.Response:

    return srpc.p.GetProject.Response(data=(await storage.get_project(req.args.id)).project)


async def add_ap_using_robot_cb(req: srpc.p.AddApUsingRobot.Request, ui: WsClient) -> None:
    async def notify(ap: common.BareActionPoint, ori: common.NamedOrientation, joi: common.ProjectRobotJoints) -> None:

        ap_evt = sevts.p.ActionPointChanged(ap)
        ap_evt.change_type = Event.Type.ADD
        await notif.broadcast_event(ap_evt)

        ori_evt = sevts.p.OrientationChanged(ori)
        ori_evt.change_type = Event.Type.ADD
        ori_evt.parent_id = ap.id

        joi_evt = sevts.p.JointsChanged(joi)
        joi_evt.change_type = Event.Type.ADD
        joi_evt.parent_id = ap.id

        await asyncio.gather(notif.broadcast_event(ori_evt), notif.broadcast_event(joi_evt))

    hlp.is_valid_identifier(req.args.name)
    proj = glob.LOCK.project_or_exception()

    async with ctx_read_lock(req.args.robot_id, glob.USERS.user_name(ui)):

        ensure_scene_started()

        unique_name(req.args.name, proj.action_points_names)

        robot_inst = get_robot_instance(req.args.robot_id)
        await check_eef_arm(robot_inst, req.args.arm_id, req.args.end_effector_id)

        if req.dry_run:
            return None

        pose, joints = await get_pose_and_joints(robot_inst, req.args.end_effector_id, req.args.arm_id)

        ap = proj.upsert_action_point(common.ActionPoint.uid(), req.args.name, pose.position)
        ori = common.NamedOrientation("default", pose.orientation)
        proj.upsert_orientation(ap.id, ori)
        joi = common.ProjectRobotJoints(
            "default", req.args.robot_id, joints, True, req.args.arm_id, req.args.end_effector_id
        )
        proj.upsert_joints(ap.id, joi)

        asyncio.ensure_future(notify(ap, ori, joi))
        return None


async def add_action_point_joints_using_robot_cb(
    req: srpc.p.AddActionPointJointsUsingRobot.Request, ui: WsClient
) -> None:

    hlp.is_valid_identifier(req.args.name)
    proj = glob.LOCK.project_or_exception()

    async with ctx_read_lock(req.args.robot_id, glob.USERS.user_name(ui)):

        ensure_scene_started()

        robot_inst = get_robot_instance(req.args.robot_id)
        await check_eef_arm(robot_inst, req.args.arm_id)

        ap = proj.bare_action_point(req.args.action_point_id)

        unique_name(req.args.name, proj.ap_joint_names(ap.id))

        new_joints = await get_robot_joints(robot_inst, req.args.arm_id)

        await ensure_write_locked(ap.id, glob.USERS.user_name(ui))

        if req.dry_run:
            return None

        prj = common.ProjectRobotJoints(
            req.args.name, req.args.robot_id, new_joints, True, req.args.arm_id, req.args.end_effector_id
        )
        proj.upsert_joints(ap.id, prj)

        evt = sevts.p.JointsChanged(prj)
        evt.change_type = Event.Type.ADD
        evt.parent_id = ap.id
        asyncio.ensure_future(notif.broadcast_event(evt))
        return None


async def update_action_point_joints_using_robot_cb(
    req: srpc.p.UpdateActionPointJointsUsingRobot.Request, ui: WsClient
) -> None:

    proj = glob.LOCK.project_or_exception()

    ensure_scene_started()

    ap, robot_joints = proj.ap_and_joints(req.args.joints_id)

    user_name = glob.USERS.user_name(ui)

    async with ctx_read_lock(robot_joints.robot_id, user_name):
        await ensure_write_locked(ap.id, user_name)

        robot_joints.joints = await get_robot_joints(get_robot_instance(robot_joints.robot_id), robot_joints.arm_id)
        robot_joints.is_valid = True

        proj.update_modified()

        evt = sevts.p.JointsChanged(robot_joints)
        evt.change_type = Event.Type.UPDATE
        asyncio.ensure_future(notif.broadcast_event(evt))
        return None


async def update_action_point_joints_cb(req: srpc.p.UpdateActionPointJoints.Request, ui: WsClient) -> None:

    proj = glob.LOCK.project_or_exception()

    ap, robot_joints = proj.ap_and_joints(req.args.joints_id)

    if {joint.name for joint in req.args.joints} != {joint.name for joint in robot_joints.joints}:
        raise Arcor2Exception("Joint names does not match the robot.")

    await ensure_write_locked(ap.id, glob.USERS.user_name(ui))

    # TODO maybe joints values should be normalized? To <0, 2pi> or to <-pi, pi>?
    robot_joints.joints = req.args.joints
    robot_joints.is_valid = True
    proj.update_modified()

    evt = sevts.p.JointsChanged(robot_joints)
    evt.change_type = Event.Type.UPDATE
    asyncio.ensure_future(notif.broadcast_event(evt))
    return None


async def remove_action_point_joints_cb(req: srpc.p.RemoveActionPointJoints.Request, ui: WsClient) -> None:
    """Removes joints from action point.

    :param req:
    :return:
    """

    proj = glob.LOCK.project_or_exception()

    for act in proj.actions:
        for param in act.parameters:
            if plugin_from_type_name(param.type).uses_robot_joints(proj, act.id, param.name, req.args.joints_id):
                raise Arcor2Exception(f"Joints used in action {act.name} (parameter {param.name}).")

    ap, _ = proj.ap_and_joints(req.args.joints_id)
    await ensure_write_locked(ap.id, glob.USERS.user_name(ui))

    joints_to_be_removed = proj.remove_joints(req.args.joints_id)

    proj.update_modified()

    evt = sevts.p.JointsChanged(joints_to_be_removed)
    evt.change_type = Event.Type.REMOVE
    asyncio.ensure_future(notif.broadcast_event(evt))
    return None


async def rename_action_point_cb(req: srpc.p.RenameActionPoint.Request, ui: WsClient) -> None:

    proj = glob.LOCK.project_or_exception()

    ap = proj.bare_action_point(req.args.action_point_id)

    if req.args.new_name == ap.name:
        raise Arcor2Exception("Name unchanged")

    hlp.is_valid_identifier(req.args.new_name)
    unique_name(req.args.new_name, proj.action_points_names)

    user_name = glob.USERS.user_name(ui)
    await ensure_write_locked(req.args.action_point_id, user_name)

    if req.dry_run:
        return None

    ap.name = req.args.new_name

    proj.update_modified()

    await glob.LOCK.write_unlock(req.args.action_point_id, user_name, True)

    evt = sevts.p.ActionPointChanged(ap)
    evt.change_type = Event.Type.UPDATE_BASE
    asyncio.ensure_future(notif.broadcast_event(evt))

    return None


def detect_ap_loop(proj: CachedProject, ap: common.BareActionPoint, new_parent_id: str) -> None:

    visited_ids: set[str] = set()
    ap = copy.deepcopy(ap)
    ap.parent = new_parent_id
    while True:

        if ap.id in visited_ids:
            raise Arcor2Exception("Loop detected!")

        visited_ids.add(ap.id)

        if ap.parent is None:
            break  # type: ignore  # this is certainly reachable

        try:
            ap = proj.bare_action_point(ap.parent)
        except Arcor2Exception:
            break


async def update_action_point_parent_cb(req: srpc.p.UpdateActionPointParent.Request, ui: WsClient) -> None:

    scene = glob.LOCK.scene_or_exception()
    proj = glob.LOCK.project_or_exception()
    user_name = glob.USERS.user_name(ui)
    ap = proj.bare_action_point(req.args.action_point_id)

    # some super basic checks (not involving other objects) are performed before locking anything
    if req.args.new_parent_id == ap.parent:
        return None

    if req.args.new_parent_id == ap.id:
        raise Arcor2Exception("AP can't be its own parent.")

    to_lock = await get_unlocked_objects(ap.parent, user_name) if ap.parent else set()
    if req.args.new_parent_id:
        to_lock.add(req.args.new_parent_id)

    async with ctx_write_lock(to_lock, user_name):

        check_ap_parent(scene, proj, req.args.new_parent_id)
        detect_ap_loop(proj, ap, req.args.new_parent_id)

        await ensure_write_locked(ap.id, user_name)  # TODO should require locked tree?

        if req.dry_run:
            return

        # Save root and parent of current AP and apply it to structures after successful update
        current_root = await glob.LOCK.get_root_id(ap.id)
        old_parent = ap.parent

        if not ap.parent and req.args.new_parent_id:
            # AP position and all orientations will become relative to the parent
            updated_aps = tr.make_global_ap_relative(scene, proj, ap, req.args.new_parent_id)

        elif ap.parent and not req.args.new_parent_id:
            # AP position and all orientations will become absolute
            updated_aps = tr.make_relative_ap_global(scene, proj, ap)
        else:

            assert ap.parent
            # AP position and all orientations will become relative to another parent
            _updated_aps = tr.make_relative_ap_global(scene, proj, ap)
            updated_aps = tr.make_global_ap_relative(scene, proj, ap, req.args.new_parent_id)

            updated_aps = set.union(updated_aps, _updated_aps)

        proj.update_child(ap.id, old_parent, req.args.new_parent_id)
        await glob.LOCK.update_write_lock(ap.id, current_root, user_name)

        assert (req.args.new_parent_id and ap.parent == req.args.new_parent_id) or (
            req.args.new_parent_id == "" and ap.parent is None
        ), f"Requested parent id: {req.args.new_parent_id}, current parent id: {ap.parent}"
        proj.update_modified()

        """
        Can't send orientation changes and then ActionPointChanged/UPDATE_BASE (or vice versa)
        because UI would display orientations wrongly (for a short moment).
        """
        # 'ap' is BareActionPoint, that does not contain orientations
        evt = sevts.p.ActionPointChanged(proj.action_point(req.args.action_point_id))
        evt.change_type = Event.Type.UPDATE
        asyncio.ensure_future(notif.broadcast_event(evt))

        for cap in updated_aps:
            evt = sevts.p.ActionPointChanged(proj.action_point(cap))
            evt.change_type = Event.Type.UPDATE
            asyncio.ensure_future(notif.broadcast_event(evt))

    await glob.LOCK.write_unlock(ap.id, user_name, True)

    return None


async def update_ap_position(
    proj: UpdateableCachedProject, ap: common.BareActionPoint, position: common.Position
) -> None:
    """Updates position of an AP and sends notification about joints that
    become invalid because of it.

    :param ap:
    :param position:
    :return:
    """

    valid_joints = [joints for joints in proj.ap_joints(ap.id) if joints.is_valid]
    proj.update_ap_position(ap.id, position)

    for joints in valid_joints:  # those are now invalid, so let's notify UI about the change

        assert not joints.is_valid

        evt = sevts.p.JointsChanged(joints)
        evt.change_type = Event.Type.UPDATE
        evt.parent_id = ap.id
        asyncio.ensure_future(notif.broadcast_event(evt))

    ap_evt = sevts.p.ActionPointChanged(ap)
    ap_evt.change_type = Event.Type.UPDATE_BASE
    asyncio.ensure_future(notif.broadcast_event(ap_evt))


async def update_action_point_position_cb(req: srpc.p.UpdateActionPointPosition.Request, ui: WsClient) -> None:

    proj = glob.LOCK.project_or_exception()
    ap = proj.bare_action_point(req.args.action_point_id)
    user_name = glob.USERS.user_name(ui)

    if req.dry_run:
        await glob.LOCK.check_lock_tree(req.args.action_point_id, user_name)
    else:
        await ensure_write_locked(req.args.action_point_id, user_name, True)

    if req.dry_run:
        return

    await update_ap_position(proj, ap, req.args.new_position)


async def update_action_point_using_robot_cb(req: srpc.p.UpdateActionPointUsingRobot.Request, ui: WsClient) -> None:

    scene = glob.LOCK.scene_or_exception()
    proj = glob.LOCK.project_or_exception()
    ensure_scene_started()
    user_name = glob.USERS.user_name(ui)

    ap = proj.bare_action_point(req.args.action_point_id)
    await ensure_write_locked(ap.id, user_name)

    async with ctx_read_lock(req.args.robot.robot_id, user_name):
        robot_inst = get_robot_instance(req.args.robot.robot_id)
        await check_eef_arm(robot_inst, req.args.robot.arm_id, req.args.robot.end_effector)
        new_pose = await get_end_effector_pose(robot_inst, req.args.robot.end_effector, req.args.robot.arm_id)

        if ap.parent:
            new_pose = tr.make_pose_rel_to_parent(scene, proj, new_pose, ap.parent)

        await update_ap_position(proj, proj.bare_action_point(req.args.action_point_id), new_pose.position)
        return None


async def add_action_point_orientation_cb(req: srpc.p.AddActionPointOrientation.Request, ui: WsClient) -> None:
    """Adds orientation and joints to the action point.

    :param req:
    :return:
    """

    proj = glob.LOCK.project_or_exception()

    ap = proj.bare_action_point(req.args.action_point_id)
    hlp.is_valid_identifier(req.args.name)
    unique_name(req.args.name, proj.ap_orientation_names(ap.id))

    await ensure_write_locked(req.args.action_point_id, glob.USERS.user_name(ui))

    if req.dry_run:
        return None

    orientation = common.NamedOrientation(req.args.name, req.args.orientation)
    proj.upsert_orientation(ap.id, orientation)

    evt = sevts.p.OrientationChanged(orientation)
    evt.change_type = Event.Type.ADD
    evt.parent_id = ap.id
    asyncio.ensure_future(notif.broadcast_event(evt))
    return None


async def update_action_point_orientation_cb(req: srpc.p.UpdateActionPointOrientation.Request, ui: WsClient) -> None:
    """Updates orientation of the action point.

    :param req:
    :return:
    """

    proj = glob.LOCK.project_or_exception()
    orientation = proj.orientation(req.args.orientation_id)
    await ensure_write_locked(orientation.id, glob.USERS.user_name(ui))

    orientation.orientation = req.args.orientation

    proj.update_modified()

    evt = sevts.p.OrientationChanged(orientation)
    evt.change_type = Event.Type.UPDATE
    asyncio.ensure_future(notif.broadcast_event(evt))
    return None


async def add_action_point_orientation_using_robot_cb(
    req: srpc.p.AddActionPointOrientationUsingRobot.Request, ui: WsClient
) -> None:
    """Adds orientation and joints to the action point.

    :param req:
    :return:
    """

    scene = glob.LOCK.scene_or_exception()
    proj = glob.LOCK.project_or_exception()
    user_name = glob.USERS.user_name(ui)

    async with ctx_read_lock(req.args.robot.robot_id, user_name):

        ensure_scene_started()

        ap = proj.bare_action_point(req.args.action_point_id)
        hlp.is_valid_identifier(req.args.name)
        unique_name(req.args.name, proj.ap_orientation_names(ap.id))
        robot_inst = get_robot_instance(req.args.robot.robot_id)
        await check_eef_arm(robot_inst, req.args.robot.arm_id, req.args.robot.end_effector)

        await ensure_write_locked(req.args.action_point_id, user_name)

        if req.dry_run:
            return None

        new_pose = await get_end_effector_pose(robot_inst, req.args.robot.end_effector, req.args.robot.arm_id)

        if ap.parent:
            new_pose = tr.make_pose_rel_to_parent(scene, proj, new_pose, ap.parent)

        orientation = common.NamedOrientation(req.args.name, new_pose.orientation)
        proj.upsert_orientation(ap.id, orientation)

        evt = sevts.p.OrientationChanged(orientation)
        evt.change_type = Event.Type.ADD
        evt.parent_id = ap.id
        asyncio.ensure_future(notif.broadcast_event(evt))
        return None


async def update_action_point_orientation_using_robot_cb(
    req: srpc.p.UpdateActionPointOrientationUsingRobot.Request, ui: WsClient
) -> None:
    """Updates orientation and joint of the action point.

    :param req:
    :return:
    """

    scene = glob.LOCK.scene_or_exception()
    proj = glob.LOCK.project_or_exception()
    user_name = glob.USERS.user_name(ui)

    async with ctx_read_lock(req.args.robot.robot_id, user_name):

        ensure_scene_started()
        robot_inst = get_robot_instance(req.args.robot.robot_id)
        await check_eef_arm(robot_inst, req.args.robot.arm_id, req.args.robot.end_effector)

        ap, ori = proj.bare_ap_and_orientation(req.args.orientation_id)

        await ensure_write_locked(ori.id, user_name)

        new_pose = await get_end_effector_pose(robot_inst, req.args.robot.end_effector, req.args.robot.arm_id)

        if ap.parent:
            new_pose = tr.make_pose_rel_to_parent(scene, proj, new_pose, ap.parent)

        ori.orientation = new_pose.orientation

        proj.update_modified()

        evt = sevts.p.OrientationChanged(ori)
        evt.change_type = Event.Type.UPDATE
        asyncio.ensure_future(notif.broadcast_event(evt))
        return None


async def remove_action_point_orientation_cb(req: srpc.p.RemoveActionPointOrientation.Request, ui: WsClient) -> None:
    """Removes orientation.

    :param req:
    :return:
    """

    proj = glob.LOCK.project_or_exception()
    user_name = glob.USERS.user_name(ui)
    ap, orientation = proj.bare_ap_and_orientation(req.args.orientation_id)

    to_lock = await get_unlocked_objects(orientation.id, user_name)
    async with ctx_write_lock(to_lock, user_name, auto_unlock=req.dry_run):
        for act in proj.actions:
            for param in act.parameters:
                if plugin_from_type_name(param.type).uses_orientation(
                    proj, act.id, param.name, req.args.orientation_id
                ):
                    raise Arcor2Exception(f"Orientation used in action {act.name} (parameter {param.name}).")

        if req.dry_run:
            return None

        await glob.LOCK.write_unlock(orientation.id, user_name)

        proj.remove_orientation(req.args.orientation_id)

        evt = sevts.p.OrientationChanged(orientation)
        evt.change_type = Event.Type.REMOVE
        asyncio.ensure_future(notif.broadcast_event(evt))
        return None


async def open_project_cb(req: srpc.p.OpenProject.Request, ui: WsClient) -> None:
    """Opens a project. This can be done even when a scene or another project
    is opened.

    :param req:
    :param ui:
    :return:
    """

    async with glob.LOCK.get_lock():

        if glob.PACKAGE_STATE.state in PackageState.RUN_STATES:
            raise Arcor2Exception("Can't open project while package runs.")

        await open_project(req.args.id)

        assert glob.LOCK.scene
        assert glob.LOCK.project

        asyncio.ensure_future(
            notify_project_opened(
                sevts.p.OpenProject(sevts.p.OpenProject.Data(glob.LOCK.scene.scene, glob.LOCK.project.project))
            )
        )

        return None


async def save_project_cb(req: srpc.p.SaveProject.Request, ui: WsClient) -> None:

    async with glob.LOCK.get_lock(req.dry_run):

        proj = glob.LOCK.project_or_exception()

        if proj.modified and not proj.has_changes:
            raise Arcor2Exception("No changes to save.")

        if req.dry_run:
            return None

        # TODO temporary code to help debugging long lasting update of project
        import time

        start = time.monotonic()
        proj.modified = await storage.update_project(proj)
        logger.info(f"Updating the project took {time.monotonic()-start:.3f}s.")

    asyncio.ensure_future(notif.broadcast_event(sevts.p.ProjectSaved()))
    return None


async def new_project_cb(req: srpc.p.NewProject.Request, ui: WsClient) -> None:

    if glob.LOCK.project:
        raise Arcor2Exception("Project has to be closed first.")

    async with ctx_write_lock(glob.LOCK.SpecialValues.PROJECT, glob.USERS.user_name(ui), dry_run=req.dry_run):
        if glob.PACKAGE_STATE.state in PackageState.RUN_STATES:
            raise Arcor2Exception("Can't create project while package runs.")

        unique_name(req.args.name, (await project_names()))

        # TODO workaround for https://gitlab.com/kinalisoft/test-it-off/project/-/issues/16
        unique_name(req.args.name, (await scene_names()))

        if await glob.LOCK.get_write_locks_count() > 1:  # project lock also counts
            raise Arcor2Exception("Project has locked objects")

        if req.dry_run:
            return None

        if glob.LOCK.scene:
            if glob.LOCK.scene.id != req.args.scene_id:
                raise Arcor2Exception("Another scene is opened.")

            # the scene might not be saved yet - another check
            # TODO workaround for https://gitlab.com/kinalisoft/test-it-off/project/-/issues/16
            if req.args.name == glob.LOCK.scene.name:
                raise Arcor2Exception("A project can't have the same name as the scene.")

            if glob.LOCK.scene.has_changes:
                await save_scene()
        else:

            if req.args.scene_id not in (await storage.get_scene_ids()):
                raise Arcor2Exception("Unknown scene id.")

            await open_scene(req.args.scene_id)

        glob.PREV_RESULTS.clear()
        glob.LOCK.project = UpdateableCachedProject(
            common.Project(
                req.args.name, req.args.scene_id, description=req.args.description, has_logic=req.args.has_logic
            )
        )

        assert glob.LOCK.scene

        # add commonly used project parameters
        from arcor2 import json  # TODO use parameter plugin

        glob.LOCK.project.upsert_parameter(
            common.ProjectParameter("scene_id", "string", json.dumps(glob.LOCK.scene.id))
        )
        glob.LOCK.project.upsert_parameter(
            common.ProjectParameter("project_id", "string", json.dumps(glob.LOCK.project.id))
        )

        asyncio.ensure_future(
            notify_project_opened(
                sevts.p.OpenProject(sevts.p.OpenProject.Data(glob.LOCK.scene.scene, glob.LOCK.project.project))
            )
        )
        return None


async def close_project_cb(req: srpc.p.CloseProject.Request, ui: WsClient) -> None:

    async with glob.LOCK.get_lock(req.dry_run):

        proj = glob.LOCK.project_or_exception()
        can_modify_scene()

        if not req.args.force and proj.has_changes:
            raise Arcor2Exception("Project has unsaved changes.")

        if req.dry_run:
            return None

        await close_project()
        return None


async def add_action_point_cb(req: srpc.p.AddActionPoint.Request, ui: WsClient) -> None:

    scene = glob.LOCK.scene_or_exception()
    proj = glob.LOCK.project_or_exception()

    async with ctx_write_lock(glob.LOCK.SpecialValues.PROJECT, glob.USERS.user_name(ui)):

        hlp.is_valid_identifier(req.args.name)
        unique_name(req.args.name, proj.action_points_names)
        check_ap_parent(scene, proj, req.args.parent)

        if req.dry_run:
            return None

        ap = proj.upsert_action_point(common.ActionPoint.uid(), req.args.name, req.args.position, req.args.parent)

        evt = sevts.p.ActionPointChanged(ap)
        evt.change_type = Event.Type.ADD
        asyncio.ensure_future(notif.broadcast_event(evt))
        return None


async def remove_action_point_cb(req: srpc.p.RemoveActionPoint.Request, ui: WsClient) -> None:

    proj = glob.LOCK.project_or_exception()

    user_name = glob.USERS.user_name(ui)
    to_lock = await get_unlocked_objects(req.args.id, user_name)
    async with ctx_write_lock(to_lock, user_name, auto_unlock=req.dry_run):

        ap = proj.bare_action_point(req.args.id)

        for proj_ap in proj.action_points_with_parent:
            if proj_ap.parent == ap.id:
                raise Arcor2Exception(f"Can't remove parent of '{proj_ap.name}' AP.")

        ap_action_ids = proj.ap_action_ids(ap.id)

        # check if AP's actions aren't involved in logic
        # TODO 'force' param to remove logical connections?
        for logic in proj.logic:
            if (
                logic.start in ap_action_ids
                or logic.end in ap_action_ids
                or (logic.condition and logic.condition.parse_what().action_id in ap_action_ids)
            ):
                raise Arcor2Exception("Remove logic connections first.")

        for act in proj.actions:

            if act.id in ap_action_ids:
                continue

            for param in act.parameters:
                if param.type == common.ActionParameter.TypeEnum.LINK:
                    parsed_link = param.parse_link()
                    linking_action = proj.action(parsed_link.action_id)
                    if parsed_link.action_id in ap_action_ids:
                        raise Arcor2Exception(f"Result of '{act.name}' is linked from '{linking_action.name}'.")

                if not param.is_value():
                    continue

                for joints in proj.ap_joints(ap.id):
                    if plugin_from_type_name(param.type).uses_robot_joints(proj, act.id, param.name, joints.id):
                        raise Arcor2Exception(
                            f"Joints {joints.name} used in action {act.name} (parameter {param.name})."
                        )

                for ori in proj.ap_orientations(ap.id):
                    if plugin_from_type_name(param.type).uses_orientation(proj, act.id, param.name, ori.id):
                        raise Arcor2Exception(
                            f"Orientation {ori.name} used in action {act.name} (parameter {param.name})."
                        )

                # TODO some hypothetical parameter type could use just bare ActionPoint (its position)

        if not await glob.LOCK.check_remove(ap.id, user_name):
            raise Arcor2Exception("Children locked")

        if req.dry_run:
            return None

        await glob.LOCK.write_unlock(req.args.id, user_name)

        proj.remove_action_point(req.args.id)

        evt = sevts.p.ActionPointChanged(ap)
        evt.change_type = Event.Type.REMOVE
        asyncio.ensure_future(notif.broadcast_event(evt))
        return None


async def copy_action_point_cb(req: srpc.p.CopyActionPoint.Request, ui: WsClient) -> None:

    proj = glob.LOCK.project_or_exception()

    async def copy_action_point(
        orig_ap: common.BareActionPoint,
        new_parent_id: None | str = None,
        position: None | common.Position = None,
    ) -> None:

        assert await glob.LOCK.is_read_locked(orig_ap.id, user_name)

        ap = proj.upsert_action_point(
            common.ActionPoint.uid(),
            make_name_unique(f"{orig_ap.name}_copy", proj.action_points_names),
            orig_ap.position if position is None else position,
            orig_ap.parent if new_parent_id is None else new_parent_id,
        )

        ap_added_evt = sevts.p.ActionPointChanged(ap)
        ap_added_evt.change_type = Event.Type.ADD
        await notif.broadcast_event(ap_added_evt)

        for ori in proj.ap_orientations(orig_ap.id):

            assert await glob.LOCK.is_read_locked(ori.id, user_name)

            new_ori = ori.copy()
            old_ori_to_new_ori[ori.id] = new_ori.id
            proj.upsert_orientation(ap.id, new_ori)

            ori_added_evt = sevts.p.OrientationChanged(new_ori)
            ori_added_evt.change_type = Event.Type.ADD
            ori_added_evt.parent_id = ap.id
            await notif.broadcast_event(ori_added_evt)

        for joints in proj.ap_joints(orig_ap.id):

            assert await glob.LOCK.is_read_locked(joints.id, user_name)

            new_joints = joints.copy()
            proj.upsert_joints(ap.id, new_joints)

            joints_added_evt = sevts.p.JointsChanged(new_joints)
            joints_added_evt.change_type = Event.Type.ADD
            joints_added_evt.parent_id = ap.id
            await notif.broadcast_event(joints_added_evt)

        action_names = proj.action_names  # action name has to be globally unique
        for act in proj.ap_actions(orig_ap.id):
            assert await glob.LOCK.is_read_locked(act.id, user_name)
            new_act = act.copy()
            new_act.name = make_name_unique(f"{act.name}_copy", action_names)
            proj.upsert_action(ap.id, new_act)
            new_action_ids.add(new_act.id)

        # find direct child-APs and copy them too
        # this can't be done in parallel for all child APs (whole hierarchy), because UI would be confused
        await asyncio.gather(
            *[
                copy_action_point(proj.action_point(child_id), ap.id)
                for child_id in proj.childs(orig_ap.id)
                if child_id in proj.action_points_ids
            ]
        )

    user_name = glob.USERS.user_name(ui)
    childs_of_original_ap = glob.LOCK.get_all_children(req.args.id)

    async with ctx_read_lock(childs_of_original_ap | {req.args.id}, user_name):

        # filter out only APs
        child_aps = {ch for ch in childs_of_original_ap if ch in proj.action_points_ids} | {req.args.id}
        logger.debug(f"Child action points of the original AP: {child_aps}")

        original_ap = proj.bare_action_point(req.args.id)

        if req.dry_run:
            return

        old_ori_to_new_ori: dict[str, str] = {}
        new_action_ids: set[str] = set()
        # let's do it within the RPC, should not take long time...
        await copy_action_point(original_ap, position=req.args.position)

        for act_id in new_action_ids:  # this has to be done once old_ori_to_new_ori is complete

            ap, new_act = proj.action_point_and_action(act_id)

            for param in new_act.parameters:

                if param.type != PosePlugin.type_name():  # TODO also handle joints and positions!
                    continue

                old_ori = proj.bare_ap_and_orientation(PosePlugin.orientation_id(proj, new_act.id, param.name))[1]
                child_orientations = {ori.id for ap_id in child_aps for ori in proj.ap_orientations(ap_id)}
                logger.debug(f"Child orientations of the original AP: {child_orientations}")

                if old_ori.id not in child_orientations:
                    logger.debug(
                        f"Orientation {old_ori.name} ({old_ori.id}) "
                        f"belongs to another AP (sub)tree, no need to update anything."
                    )
                    continue

                # orientation belongs to the tree being copied so it has to be updated

                # TODO this is hacky - plugins are missing methods to set/update parameters
                from arcor2 import json

                try:
                    new_ori_id = old_ori_to_new_ori[old_ori.id]
                except KeyError:
                    logger.error(f"Failed to find a new orientation ID for {old_ori.id}.")
                else:
                    logger.debug(f"Updating orientation from {old_ori.id} to {new_ori_id}.")
                    param.value = json.dumps(new_ori_id)

            action_added_evt = sevts.p.ActionChanged(new_act)
            action_added_evt.change_type = Event.Type.ADD
            action_added_evt.parent_id = ap.id
            await notif.broadcast_event(action_added_evt)


async def add_action_cb(req: srpc.p.AddAction.Request, ui: WsClient) -> None:
    """Adds new action to project.

    Used also when duplicating action.
    """

    scene = glob.LOCK.scene_or_exception()
    proj = glob.LOCK.project_or_exception()

    # When duplicating action AP cannot be removed, no need to lock
    user_name = glob.USERS.user_name(ui)
    to_lock = await get_unlocked_objects(req.args.action_point_id, user_name)
    async with ctx_write_lock(to_lock, user_name):
        ap = proj.bare_action_point(req.args.action_point_id)

        unique_name(req.args.name, proj.action_names)

        new_action = common.Action(req.args.name, req.args.type, parameters=req.args.parameters, flows=req.args.flows)

        action_meta = find_object_action(glob.OBJECT_TYPES, scene, new_action)

        updated_project = copy.deepcopy(proj)
        updated_project.upsert_action(req.args.action_point_id, new_action)

        check_flows(updated_project, new_action, action_meta)
        check_action_params(glob.OBJECT_TYPES, scene, updated_project, new_action, action_meta)

        if req.dry_run:
            return None

        proj.upsert_action(ap.id, new_action)

        evt = sevts.p.ActionChanged(new_action)
        evt.change_type = Event.Type.ADD
        evt.parent_id = ap.id
        asyncio.ensure_future(notif.broadcast_event(evt))
        return None


async def update_action_cb(req: srpc.p.UpdateAction.Request, ui: WsClient) -> None:

    scene = glob.LOCK.scene_or_exception()
    proj = glob.LOCK.project_or_exception()

    updated_project = copy.deepcopy(proj)

    updated_action = updated_project.action(req.args.action_id)

    if req.args.parameters is not None:
        updated_action.parameters = req.args.parameters
    if req.args.flows is not None:
        updated_action.flows = req.args.flows

    updated_action_meta = find_object_action(glob.OBJECT_TYPES, scene, updated_action)

    check_flows(updated_project, updated_action, updated_action_meta)
    check_action_params(glob.OBJECT_TYPES, scene, updated_project, updated_action, updated_action_meta)

    await ensure_write_locked(req.args.action_id, glob.USERS.user_name(ui))

    if req.dry_run:
        return None

    orig_action = proj.action(req.args.action_id)
    orig_action.parameters = updated_action.parameters
    proj.update_modified()

    evt = sevts.p.ActionChanged(updated_action)
    evt.change_type = Event.Type.UPDATE
    asyncio.ensure_future(notif.broadcast_event(evt))
    return None


async def remove_action_cb(req: srpc.p.RemoveAction.Request, ui: WsClient) -> None:
    def check_action_usage(proj: CachedProject, action: common.Action) -> None:

        # check parameters
        for act in proj.actions:
            for param in act.parameters:
                if param.type == common.ActionParameter.TypeEnum.LINK:
                    link = param.parse_link()
                    if action.id == link.action_id:
                        raise Arcor2Exception(f"Action output used as parameter of {act.name}/{param.name}.")

        # check logic
        for log in proj.logic:

            if log.start == action.id or log.end == action.id:
                raise Arcor2Exception("Action used in logic.")

            if log.condition:
                action_id, _, _ = log.condition.what.split("/")

                if action_id == action.id:
                    raise Arcor2Exception("Action used in condition.")

    proj = glob.LOCK.project_or_exception()
    user_name = glob.USERS.user_name(ui)
    to_lock = await get_unlocked_objects(req.args.id, user_name)
    async with ctx_write_lock(to_lock, user_name, auto_unlock=req.dry_run):

        ap, action = proj.action_point_and_action(req.args.id)
        check_action_usage(proj, action)

        if req.dry_run:
            return None

        await glob.LOCK.write_unlock(req.args.id, user_name)

        proj.remove_action(req.args.id)
        glob.remove_prev_result(action.id)

        evt = sevts.p.ActionChanged(action.bare)
        evt.change_type = Event.Type.REMOVE
        asyncio.ensure_future(notif.broadcast_event(evt))
        return None


async def add_logic_item_cb(req: srpc.p.AddLogicItem.Request, ui: WsClient) -> None:

    scene = glob.LOCK.scene_or_exception()
    proj = glob.LOCK.project_or_exception(must_have_logic=True)
    user_name = glob.USERS.user_name(ui)

    to_lock = await get_unlocked_objects([req.args.start, req.args.end], user_name)
    async with ctx_write_lock(to_lock, user_name):
        logic_item = common.LogicItem(req.args.start, req.args.end, req.args.condition)
        check_logic_item(glob.OBJECT_TYPES, scene, proj, logic_item)

        if logic_item.start != logic_item.START:
            updated_project = copy.deepcopy(proj)
            updated_project.upsert_logic_item(logic_item)
            check_for_loops(updated_project, logic_item.parse_start().start_action_id)

        if req.dry_run:
            return

        proj.upsert_logic_item(logic_item)

        evt = sevts.p.LogicItemChanged(logic_item)
        evt.change_type = Event.Type.ADD
        asyncio.ensure_future(notif.broadcast_event(evt))

    await glob.LOCK.write_unlock(
        [item for item in (req.args.start, req.args.end) if item not in to_lock], user_name, True
    )
    return None


async def update_logic_item_cb(req: srpc.p.UpdateLogicItem.Request, ui: WsClient) -> None:
    # TODO lock RPC when used

    scene = glob.LOCK.scene_or_exception()
    proj = glob.LOCK.project_or_exception(must_have_logic=True)

    updated_project = copy.deepcopy(proj)
    updated_logic_item = updated_project.logic_item(req.args.logic_item_id)

    updated_logic_item.start = req.args.start
    updated_logic_item.end = req.args.end
    updated_logic_item.condition = req.args.condition

    check_logic_item(glob.OBJECT_TYPES, scene, updated_project, updated_logic_item)

    if updated_logic_item.start != updated_logic_item.START:
        check_for_loops(updated_project, updated_logic_item.parse_start().start_action_id)

    if req.dry_run:
        return

    proj.upsert_logic_item(updated_logic_item)

    evt = sevts.p.LogicItemChanged(updated_logic_item)
    evt.change_type = Event.Type.UPDATE
    asyncio.ensure_future(notif.broadcast_event(evt))
    return None


async def remove_logic_item_cb(req: srpc.p.RemoveLogicItem.Request, ui: WsClient) -> None:

    proj = glob.LOCK.project_or_exception(must_have_logic=True)
    logic_item = proj.logic_item(req.args.logic_item_id)

    user_name = glob.USERS.user_name(ui)
    to_lock = await get_unlocked_objects([logic_item.start, logic_item.end], user_name)
    async with ctx_write_lock(to_lock, user_name):
        # TODO is it necessary to check something here?
        proj.remove_logic_item(req.args.logic_item_id)

        evt = sevts.p.LogicItemChanged(logic_item)
        evt.change_type = Event.Type.REMOVE
        asyncio.ensure_future(notif.broadcast_event(evt))

    await glob.LOCK.write_unlock(
        [item for item in (logic_item.start, logic_item.end) if item not in to_lock], user_name, True
    )
    return None


async def add_project_parameter_cb(req: srpc.p.AddProjectParameter.Request, ui: WsClient) -> None:

    proj = glob.LOCK.project_or_exception()

    async with ctx_write_lock(glob.LOCK.SpecialValues.PROJECT, glob.USERS.user_name(ui)):

        pparam = common.ProjectParameter(req.args.name, req.args.type, req.args.value)
        check_project_parameter(proj, pparam)

        if req.dry_run:
            return

        proj.upsert_parameter(pparam)

        evt = sevts.p.ProjectParameterChanged(pparam)
        evt.change_type = Event.Type.ADD
        asyncio.ensure_future(notif.broadcast_event(evt))
        return None


async def update_project_parameter_cb(req: srpc.p.UpdateProjectParameter.Request, ui: WsClient) -> None:

    proj = glob.LOCK.project_or_exception()
    param = proj.parameter(req.args.id)
    user_name = glob.USERS.user_name(ui)

    await ensure_write_locked(req.args.id, user_name)

    updated_param = copy.deepcopy(param)

    if req.args.name is not None:
        updated_param.name = req.args.name
    if req.args.value is not None:
        updated_param.value = req.args.value

    check_project_parameter(proj, updated_param)

    if req.dry_run:
        return

    proj.upsert_parameter(updated_param)

    evt = sevts.p.ProjectParameterChanged(updated_param)
    evt.change_type = Event.Type.UPDATE
    asyncio.create_task(notif.broadcast_event(evt))

    await glob.LOCK.write_unlock(param.id, user_name, True)


async def remove_project_parameter_cb(req: srpc.p.RemoveProjectParameter.Request, ui: WsClient) -> None:

    proj = glob.LOCK.project_or_exception()
    pparam = proj.parameter(req.args.id)

    user_name = glob.USERS.user_name(ui)
    to_lock = await get_unlocked_objects(req.args.id, user_name)
    async with ctx_write_lock(to_lock, user_name, auto_unlock=req.dry_run):

        # check for usage
        for act in proj.actions:
            for param in act.parameters:
                if (
                    param.type == common.ActionParameter.TypeEnum.PROJECT_PARAMETER
                    and param.str_from_value() == pparam.id
                ):
                    raise Arcor2Exception(f"Project parameter used in {act.name} action.")

        if req.dry_run:
            return

        await glob.LOCK.write_unlock(req.args.id, user_name)

        proj.remove_parameter(pparam.id)

        evt = sevts.p.ProjectParameterChanged(pparam)
        evt.change_type = Event.Type.REMOVE
        asyncio.ensure_future(notif.broadcast_event(evt))


async def delete_project_cb(req: srpc.p.DeleteProject.Request, ui: WsClient) -> None:

    if glob.LOCK.project:
        raise Arcor2Exception("Project has to be closed first.")

    user_name = glob.USERS.user_name(ui)

    async with ctx_write_lock(req.args.id, user_name, auto_unlock=False):
        project = await storage.get_project(req.args.id)
        await glob.LOCK.write_unlock(req.args.id, user_name)
        await storage.delete_project(req.args.id)

        evt = sevts.p.ProjectChanged(project.bare)
        evt.change_type = Event.Type.REMOVE
        asyncio.ensure_future(notif.broadcast_event(evt))
        return None


async def rename_project_cb(req: srpc.p.RenameProject.Request, ui: WsClient) -> None:

    unique_name(req.args.new_name, (await project_names()))

    # TODO workaround for https://gitlab.com/kinalisoft/test-it-off/project/-/issues/16
    unique_name(req.args.new_name, (await scene_names()))

    user_name = glob.USERS.user_name(ui)

    await ensure_write_locked(req.args.project_id, user_name)

    if req.dry_run:
        return None

    async with managed_project(req.args.project_id) as project:

        project.name = req.args.new_name
        project.update_modified()

        evt = sevts.p.ProjectChanged(project.bare)
        evt.change_type = Event.Type.UPDATE_BASE
        asyncio.ensure_future(notif.broadcast_event(evt))

    await glob.LOCK.write_unlock(req.args.project_id, user_name)
    return None


async def copy_project_cb(req: srpc.p.CopyProject.Request, ui: WsClient) -> None:

    async with ctx_write_lock(req.args.source_id, glob.USERS.user_name(ui)):
        unique_name(req.args.target_name, (await project_names()))

        if req.dry_run:
            return None

        async with managed_project(req.args.source_id, make_copy=True) as project:

            project.name = req.args.target_name

            evt = sevts.p.ProjectChanged(project.bare)
            evt.change_type = Event.Type.UPDATE_BASE
            asyncio.ensure_future(notif.broadcast_event(evt))

        return None


async def update_project_description_cb(req: srpc.p.UpdateProjectDescription.Request, ui: WsClient) -> None:

    async with ctx_write_lock(req.args.project_id, glob.USERS.user_name(ui)):
        async with managed_project(req.args.project_id) as project:

            project.description = req.args.new_description
            project.update_modified()

            evt = sevts.p.ProjectChanged(project.bare)
            evt.change_type = Event.Type.UPDATE_BASE
            asyncio.ensure_future(notif.broadcast_event(evt))
        return None


async def update_project_has_logic_cb(req: srpc.p.UpdateProjectHasLogic.Request, ui: WsClient) -> None:

    async with ctx_write_lock(req.args.project_id, glob.USERS.user_name(ui)):
        async with managed_project(req.args.project_id) as project:

            if project.has_logic and not req.args.new_has_logic:
                project.clear_logic()

                """
                TODO

                if glob.LOCK.project and glob.LOCK.project.id == req.args.project_id:
                ...send remove event for each logic item?
                """

            project.has_logic = req.args.new_has_logic
            project.update_modified()

            evt = sevts.p.ProjectChanged(project.bare)
            evt.change_type = Event.Type.UPDATE_BASE
            asyncio.ensure_future(notif.broadcast_event(evt))
        return None


async def rename_action_point_joints_cb(req: srpc.p.RenameActionPointJoints.Request, ui: WsClient) -> None:

    proj = glob.LOCK.project_or_exception()
    ap, joints = proj.ap_and_joints(req.args.joints_id)

    hlp.is_valid_identifier(req.args.new_name)
    unique_name(req.args.new_name, proj.ap_joint_names(ap.id))

    await ensure_write_locked(ap.id, glob.USERS.user_name(ui))

    if req.dry_run:
        return None

    joints.name = req.args.new_name
    proj.update_modified()

    evt = sevts.p.JointsChanged(joints)
    evt.change_type = Event.Type.UPDATE_BASE
    asyncio.ensure_future(notif.broadcast_event(evt))

    return None


async def rename_action_point_orientation_cb(req: srpc.p.RenameActionPointOrientation.Request, ui: WsClient) -> None:

    proj = glob.LOCK.project_or_exception()
    ap, ori = proj.bare_ap_and_orientation(req.args.orientation_id)

    hlp.is_valid_identifier(req.args.new_name)
    unique_name(req.args.new_name, proj.ap_orientation_names(ap.id))

    await ensure_write_locked(ori.id, glob.USERS.user_name(ui))

    if req.dry_run:
        return None

    ori.name = req.args.new_name
    proj.update_modified()

    evt = sevts.p.OrientationChanged(ori)
    evt.change_type = Event.Type.UPDATE_BASE
    asyncio.ensure_future(notif.broadcast_event(evt))

    return None


async def rename_action_cb(req: srpc.p.RenameAction.Request, ui: WsClient) -> None:

    proj = glob.LOCK.project_or_exception()
    unique_name(req.args.new_name, proj.action_names)
    user_name = glob.USERS.user_name(ui)

    await ensure_write_locked(req.args.action_id, user_name)

    if req.dry_run:
        return None

    act = proj.action(req.args.action_id)
    act.name = req.args.new_name

    proj.update_modified()

    await glob.LOCK.write_unlock(req.args.action_id, user_name, True)

    evt = sevts.p.ActionChanged(act)
    evt.change_type = Event.Type.UPDATE_BASE
    asyncio.ensure_future(notif.broadcast_event(evt))

    return None
