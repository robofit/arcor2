import asyncio
import copy
from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator, Dict, List, Optional, Set

from websockets.server import WebSocketServerProtocol as WsClient

from arcor2 import helpers as hlp
from arcor2 import transformations as tr
from arcor2.cached import CachedProjectException, CachedScene, UpdateableCachedProject
from arcor2.data import common
from arcor2.data.events import Event, PackageState
from arcor2.exceptions import Arcor2Exception
from arcor2.logic import LogicContainer, check_for_loops
from arcor2.object_types.abstract import Robot
from arcor2.parameter_plugins.base import ParameterPluginException
from arcor2.parameter_plugins.utils import plugin_from_type_name
from arcor2_arserver import globals as glob
from arcor2_arserver import notifications as notif
from arcor2_arserver import project
from arcor2_arserver.clients import persistent_storage as storage
from arcor2_arserver.decorators import no_project, project_needed, scene_needed
from arcor2_arserver.helpers import unique_name
from arcor2_arserver.objects_actions import get_types_dict
from arcor2_arserver.project import (
    check_action_params,
    check_flows,
    close_project,
    find_object_action,
    open_project,
    project_names,
    project_problems,
)
from arcor2_arserver.robot import get_end_effector_pose, get_robot_joints
from arcor2_arserver.scene import can_modify_scene, ensure_scene_started, get_instance, open_scene
from arcor2_arserver_data import events as sevts
from arcor2_arserver_data import rpc as srpc


@asynccontextmanager
async def managed_project(project_id: str, make_copy: bool = False) -> AsyncGenerator[UpdateableCachedProject, None]:

    save_back = False

    if glob.PROJECT and glob.PROJECT.id == project_id:
        if make_copy:
            project = copy.deepcopy(glob.PROJECT)
            save_back = True
        else:
            project = glob.PROJECT
    else:
        save_back = True
        project = UpdateableCachedProject(await storage.get_project(project_id))

    if make_copy:
        project.id = common.Project.uid()

    try:
        yield project
    finally:
        if save_back:
            asyncio.ensure_future(storage.update_project(project.project))


@scene_needed
@project_needed
async def cancel_action_cb(req: srpc.p.CancelAction.Request, ui: WsClient) -> None:

    assert glob.SCENE
    assert glob.PROJECT

    if not glob.RUNNING_ACTION:
        raise Arcor2Exception("No action is running.")

    action = glob.PROJECT.action(glob.RUNNING_ACTION)
    obj_id, action_name = action.parse_type()
    obj = get_instance(obj_id)

    if not find_object_action(glob.SCENE, action).meta.cancellable:
        raise Arcor2Exception("Action is not cancellable.")

    try:
        action_method = getattr(obj, action_name)
        cancel_method = getattr(obj, obj.CANCEL_MAPPING[action_method.__name__])
    except AttributeError as e:
        raise Arcor2Exception("Internal error.") from e

    cancel_params: Dict[str, Any] = {}

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


@scene_needed
@project_needed
async def execute_action_cb(req: srpc.p.ExecuteAction.Request, ui: WsClient) -> None:

    assert glob.SCENE
    assert glob.PROJECT

    ensure_scene_started()

    if glob.RUNNING_ACTION:
        raise Arcor2Exception(
            f"Action {glob.RUNNING_ACTION} is being executed. " f"Only one action can be executed at a time."
        )

    action = glob.PROJECT.action(req.args.action_id)

    obj_id, action_name = action.parse_type()

    params: List[Any] = []

    for param in action.parameters:

        if param.type == common.ActionParameter.TypeEnum.LINK:

            parsed_link = param.parse_link()
            try:
                results = project.PREV_RESULTS[parsed_link.action_id]
            except KeyError:
                prev_action = glob.PROJECT.action(parsed_link.action_id)
                raise Arcor2Exception(f"Action '{prev_action.name}' has to be executed first.")

            # an action result could be a tuple or a single value
            if isinstance(results, tuple):
                params.append(results[parsed_link.output_index])
            else:
                assert parsed_link.output_index == 0
                params.append(results)

        elif param.type == common.ActionParameter.TypeEnum.CONSTANT:
            const = glob.PROJECT.constant(param.value)
            # TODO use plugin to get the value
            import json

            params.append(json.loads(const.value))
        else:

            try:
                params.append(
                    plugin_from_type_name(param.type).parameter_execution_value(
                        get_types_dict(), glob.SCENE, glob.PROJECT, action.id, param.name
                    )
                )
            except ParameterPluginException as e:
                glob.logger.error(e)
                raise Arcor2Exception(f"Failed to get value for parameter {param.name}.")

    obj = get_instance(obj_id)

    if isinstance(obj, Robot):
        if obj.move_in_progress:
            raise Arcor2Exception("Can't execute actions while the robot moves.")

    if not hasattr(obj, action_name):
        raise Arcor2Exception("Internal error: object does not have the requested method.")

    if req.dry_run:
        return

    glob.RUNNING_ACTION = action.id
    glob.RUNNING_ACTION_PARAMS = params

    glob.logger.debug(f"Running action {action.name} ({type(obj)}/{action_name}), params: {params}.")

    # schedule execution and return success
    asyncio.ensure_future(project.execute_action(getattr(obj, action_name), params))
    return None


async def project_info(
    project_id: str, scenes_lock: asyncio.Lock, scenes: Dict[str, CachedScene]
) -> srpc.p.ListProjects.Response.Data:

    project = await storage.get_project(project_id)

    assert project.modified is not None

    pd = srpc.p.ListProjects.Response.Data(
        id=project.id, desc=project.desc, name=project.name, scene_id=project.scene_id, modified=project.modified
    )

    try:
        cached_project = UpdateableCachedProject(project)
    except CachedProjectException as e:
        pd.problems.append(str(e))
        return pd

    try:
        async with scenes_lock:
            if project.scene_id not in scenes:
                scenes[project.scene_id] = CachedScene(await storage.get_scene(project.scene_id))
    except storage.ProjectServiceException:
        pd.problems.append("Scene does not exist.")
        return pd

    pd.problems = project_problems(scenes[project.scene_id], cached_project)
    pd.valid = not pd.problems

    if not pd.valid:
        return pd

    try:
        # TODO call build service!!!
        pd.executable = True
    except Arcor2Exception as e:
        pd.problems.append(str(e))

    return pd


async def list_projects_cb(req: srpc.p.ListProjects.Request, ui: WsClient) -> srpc.p.ListProjects.Response:

    projects = await storage.get_projects()

    scenes_lock = asyncio.Lock()
    scenes: Dict[str, CachedScene] = {}

    resp = srpc.p.ListProjects.Response()
    tasks = [project_info(project_iddesc.id, scenes_lock, scenes) for project_iddesc in projects.items]
    resp.data = await asyncio.gather(*tasks)
    return resp


@scene_needed
@project_needed
async def add_action_point_joints_using_robot_cb(
    req: srpc.p.AddActionPointJointsUsingRobot.Request, ui: WsClient
) -> None:

    ensure_scene_started()

    assert glob.SCENE
    assert glob.PROJECT

    ap = glob.PROJECT.bare_action_point(req.args.action_point_id)

    hlp.is_valid_identifier(req.args.name)
    unique_name(req.args.name, glob.PROJECT.ap_joint_names(ap.id))

    new_joints = await get_robot_joints(req.args.robot_id)

    if req.dry_run:
        return None

    prj = common.ProjectRobotJoints(req.args.name, req.args.robot_id, new_joints, True)
    glob.PROJECT.upsert_joints(ap.id, prj)

    evt = sevts.p.JointsChanged(prj)
    evt.change_type = Event.Type.ADD
    evt.parent_id = ap.id
    asyncio.ensure_future(notif.broadcast_event(evt))
    return None


@scene_needed
@project_needed
async def update_action_point_joints_using_robot_cb(
    req: srpc.p.UpdateActionPointJointsUsingRobot.Request, ui: WsClient
) -> None:

    ensure_scene_started()

    assert glob.SCENE
    assert glob.PROJECT

    robot_joints = glob.PROJECT.joints(req.args.joints_id)
    robot_joints.joints = await get_robot_joints(robot_joints.robot_id)
    robot_joints.is_valid = True

    glob.PROJECT.update_modified()

    evt = sevts.p.JointsChanged(robot_joints)
    evt.change_type = Event.Type.UPDATE
    asyncio.ensure_future(notif.broadcast_event(evt))
    return None


@scene_needed
@project_needed
async def update_action_point_joints_cb(req: srpc.p.UpdateActionPointJoints.Request, ui: WsClient) -> None:

    assert glob.SCENE
    assert glob.PROJECT

    robot_joints = glob.PROJECT.joints(req.args.joints_id)

    if {joint.name for joint in req.args.joints} != {joint.name for joint in robot_joints.joints}:
        raise Arcor2Exception("Joint names does not match the robot.")

    # TODO maybe joints values should be normalized? To <0, 2pi> or to <-pi, pi>?
    robot_joints.joints = req.args.joints
    robot_joints.is_valid = True
    glob.PROJECT.update_modified()

    evt = sevts.p.JointsChanged(robot_joints)
    evt.change_type = Event.Type.UPDATE
    asyncio.ensure_future(notif.broadcast_event(evt))
    return None


@scene_needed
@project_needed
async def remove_action_point_joints_cb(req: srpc.p.RemoveActionPointJoints.Request, ui: WsClient) -> None:
    """Removes joints from action point.

    :param req:
    :return:
    """

    assert glob.SCENE
    assert glob.PROJECT

    for act in glob.PROJECT.actions:
        for param in act.parameters:
            if plugin_from_type_name(param.type).uses_robot_joints(
                glob.PROJECT, act.id, param.name, req.args.joints_id
            ):
                raise Arcor2Exception(f"Joints used in action {act.name} (parameter {param.name}).")

    joints_to_be_removed = glob.PROJECT.remove_joints(req.args.joints_id)

    glob.PROJECT.update_modified()

    evt = sevts.p.JointsChanged(joints_to_be_removed)
    evt.change_type = Event.Type.REMOVE
    asyncio.ensure_future(notif.broadcast_event(evt))
    return None


@scene_needed
@project_needed
async def rename_action_point_cb(req: srpc.p.RenameActionPoint.Request, ui: WsClient) -> None:

    assert glob.SCENE
    assert glob.PROJECT

    ap = glob.PROJECT.bare_action_point(req.args.action_point_id)

    if req.args.new_name == ap.name:
        return None

    hlp.is_valid_identifier(req.args.new_name)
    unique_name(req.args.new_name, glob.PROJECT.action_points_names)

    if req.dry_run:
        return None

    ap.name = req.args.new_name

    glob.PROJECT.update_modified()

    evt = sevts.p.ActionPointChanged(ap)
    evt.change_type = Event.Type.UPDATE_BASE
    asyncio.ensure_future(notif.broadcast_event(evt))
    return None


def detect_ap_loop(ap: common.BareActionPoint, new_parent_id: str) -> None:

    assert glob.PROJECT

    visited_ids: Set[str] = set()
    ap = copy.deepcopy(ap)
    ap.parent = new_parent_id
    while True:

        if ap.id in visited_ids:
            raise Arcor2Exception("Loop detected!")

        visited_ids.add(ap.id)

        if ap.parent is None:
            break  # type: ignore  # this is certainly reachable

        try:
            ap = glob.PROJECT.bare_action_point(ap.parent)
        except Arcor2Exception:
            break


@scene_needed
@project_needed
async def update_action_point_parent_cb(req: srpc.p.UpdateActionPointParent.Request, ui: WsClient) -> None:

    assert glob.SCENE
    assert glob.PROJECT

    ap = glob.PROJECT.bare_action_point(req.args.action_point_id)

    if req.args.new_parent_id == ap.parent:
        return None

    check_ap_parent(req.args.new_parent_id)
    detect_ap_loop(ap, req.args.new_parent_id)

    if req.dry_run:
        return

    if not ap.parent and req.args.new_parent_id:
        # AP position and all orientations will become relative to the parent
        tr.make_global_ap_relative(glob.SCENE, glob.PROJECT, ap, req.args.new_parent_id)

    elif ap.parent and not req.args.new_parent_id:
        # AP position and all orientations will become absolute
        tr.make_relative_ap_global(glob.SCENE, glob.PROJECT, ap)
    else:

        assert ap.parent

        # AP position and all orientations will become relative to another parent
        tr.make_relative_ap_global(glob.SCENE, glob.PROJECT, ap)
        tr.make_global_ap_relative(glob.SCENE, glob.PROJECT, ap, req.args.new_parent_id)

    ap.parent = req.args.new_parent_id
    glob.PROJECT.update_modified()

    """
    Can't send orientation changes and then ActionPointChanged/UPDATE_BASE (or vice versa)
    because UI would display orientations wrongly (for a short moment).
    """
    # 'ap' is BareActionPoint, that does not contain orientations
    evt = sevts.p.ActionPointChanged(glob.PROJECT.action_point(req.args.action_point_id))
    evt.change_type = Event.Type.UPDATE
    asyncio.ensure_future(notif.broadcast_event(evt))
    return None


async def update_ap_position(ap: common.BareActionPoint, position: common.Position) -> None:
    """Updates position of an AP and sends notification about joints that
    become invalid because of it.

    :param ap_id:
    :param position:
    :return:
    """

    assert glob.PROJECT

    valid_joints = [joints for joints in glob.PROJECT.ap_joints(ap.id) if joints.is_valid]
    glob.PROJECT.update_ap_position(ap.id, position)

    for joints in valid_joints:  # those are now invalid, so let's notify UI about the change

        assert not joints.is_valid

        evt = sevts.p.JointsChanged(joints)
        evt.change_type = Event.Type.UPDATE
        evt.parent_id = ap.id
        asyncio.ensure_future(notif.broadcast_event(evt))

    ap_evt = sevts.p.ActionPointChanged(ap)
    ap_evt.change_type = Event.Type.UPDATE_BASE
    asyncio.ensure_future(notif.broadcast_event(ap_evt))


@scene_needed
@project_needed
async def update_action_point_position_cb(req: srpc.p.UpdateActionPointPosition.Request, ui: WsClient) -> None:

    assert glob.PROJECT

    ap = glob.PROJECT.bare_action_point(req.args.action_point_id)

    if req.dry_run:
        return

    await update_ap_position(ap, req.args.new_position)


@scene_needed
@project_needed
async def update_action_point_using_robot_cb(req: srpc.p.UpdateActionPointUsingRobot.Request, ui: WsClient) -> None:

    ensure_scene_started()

    assert glob.SCENE
    assert glob.PROJECT

    ap = glob.PROJECT.bare_action_point(req.args.action_point_id)
    new_pose = await get_end_effector_pose(req.args.robot.robot_id, req.args.robot.end_effector)

    if ap.parent:
        new_pose = tr.make_pose_rel_to_parent(glob.SCENE, glob.PROJECT, new_pose, ap.parent)

    await update_ap_position(glob.PROJECT.bare_action_point(req.args.action_point_id), new_pose.position)
    return None


@scene_needed
@project_needed
async def add_action_point_orientation_cb(req: srpc.p.AddActionPointOrientation.Request, ui: WsClient) -> None:
    """Adds orientation and joints to the action point.

    :param req:
    :return:
    """

    assert glob.SCENE
    assert glob.PROJECT

    ap = glob.PROJECT.bare_action_point(req.args.action_point_id)
    hlp.is_valid_identifier(req.args.name)
    unique_name(req.args.name, glob.PROJECT.ap_orientation_names(ap.id))

    if req.dry_run:
        return None

    orientation = common.NamedOrientation(req.args.name, req.args.orientation)
    glob.PROJECT.upsert_orientation(ap.id, orientation)

    evt = sevts.p.OrientationChanged(orientation)
    evt.change_type = Event.Type.ADD
    evt.parent_id = ap.id
    asyncio.ensure_future(notif.broadcast_event(evt))
    return None


@scene_needed
@project_needed
async def update_action_point_orientation_cb(req: srpc.p.UpdateActionPointOrientation.Request, ui: WsClient) -> None:
    """Updates orientation of the action point.

    :param req:
    :return:
    """

    assert glob.SCENE
    assert glob.PROJECT

    orientation = glob.PROJECT.orientation(req.args.orientation_id)
    orientation.orientation = req.args.orientation

    glob.PROJECT.update_modified()

    evt = sevts.p.OrientationChanged(orientation)
    evt.change_type = Event.Type.UPDATE
    asyncio.ensure_future(notif.broadcast_event(evt))
    return None


@scene_needed
@project_needed
async def add_action_point_orientation_using_robot_cb(
    req: srpc.p.AddActionPointOrientationUsingRobot.Request, ui: WsClient
) -> None:
    """Adds orientation and joints to the action point.

    :param req:
    :return:
    """

    ensure_scene_started()

    assert glob.SCENE
    assert glob.PROJECT

    ap = glob.PROJECT.bare_action_point(req.args.action_point_id)
    hlp.is_valid_identifier(req.args.name)
    unique_name(req.args.name, glob.PROJECT.ap_orientation_names(ap.id))

    if req.dry_run:
        return None

    new_pose = await get_end_effector_pose(req.args.robot.robot_id, req.args.robot.end_effector)

    if ap.parent:
        new_pose = tr.make_pose_rel_to_parent(glob.SCENE, glob.PROJECT, new_pose, ap.parent)

    orientation = common.NamedOrientation(req.args.name, new_pose.orientation)
    glob.PROJECT.upsert_orientation(ap.id, orientation)

    evt = sevts.p.OrientationChanged(orientation)
    evt.change_type = Event.Type.ADD
    evt.parent_id = ap.id
    asyncio.ensure_future(notif.broadcast_event(evt))
    return None


@scene_needed
@project_needed
async def update_action_point_orientation_using_robot_cb(
    req: srpc.p.UpdateActionPointOrientationUsingRobot.Request, ui: WsClient
) -> None:
    """Updates orientation and joint of the action point.

    :param req:
    :return:
    """

    ensure_scene_started()

    assert glob.SCENE
    assert glob.PROJECT

    ap, ori = glob.PROJECT.bare_ap_and_orientation(req.args.orientation_id)

    new_pose = await get_end_effector_pose(req.args.robot.robot_id, req.args.robot.end_effector)

    if ap.parent:
        new_pose = tr.make_pose_rel_to_parent(glob.SCENE, glob.PROJECT, new_pose, ap.parent)

    ori.orientation = new_pose.orientation

    glob.PROJECT.update_modified()

    evt = sevts.p.OrientationChanged(ori)
    evt.change_type = Event.Type.UPDATE
    asyncio.ensure_future(notif.broadcast_event(evt))
    return None


@scene_needed
@project_needed
async def remove_action_point_orientation_cb(req: srpc.p.RemoveActionPointOrientation.Request, ui: WsClient) -> None:
    """Removes orientation.

    :param req:
    :return:
    """

    assert glob.SCENE
    assert glob.PROJECT

    ap, orientation = glob.PROJECT.bare_ap_and_orientation(req.args.orientation_id)

    for act in glob.PROJECT.actions:
        for param in act.parameters:
            if plugin_from_type_name(param.type).uses_orientation(
                glob.PROJECT, act.id, param.name, req.args.orientation_id
            ):
                raise Arcor2Exception(f"Orientation used in action {act.name} (parameter {param.name}).")

    if req.dry_run:
        return None

    glob.PROJECT.remove_orientation(req.args.orientation_id)

    evt = sevts.p.OrientationChanged(orientation)
    evt.change_type = Event.Type.REMOVE
    asyncio.ensure_future(notif.broadcast_event(evt))
    return None


async def open_project_cb(req: srpc.p.OpenProject.Request, ui: WsClient) -> None:

    if glob.PACKAGE_STATE.state in PackageState.RUN_STATES:
        raise Arcor2Exception("Can't open project while package runs.")

    # TODO validate using project_problems?
    await open_project(req.args.id)

    assert glob.SCENE
    assert glob.PROJECT

    asyncio.ensure_future(
        notif.broadcast_event(sevts.p.OpenProject(sevts.p.OpenProject.Data(glob.SCENE.scene, glob.PROJECT.project)))
    )

    return None


@scene_needed
@project_needed
async def save_project_cb(req: srpc.p.SaveProject.Request, ui: WsClient) -> None:

    assert glob.SCENE
    assert glob.PROJECT

    glob.PROJECT.modified = await storage.update_project(glob.PROJECT.project)
    asyncio.ensure_future(notif.broadcast_event(sevts.p.ProjectSaved()))
    return None


@no_project
async def new_project_cb(req: srpc.p.NewProject.Request, ui: WsClient) -> None:

    if glob.PACKAGE_STATE.state in PackageState.RUN_STATES:
        raise Arcor2Exception("Can't create project while package runs.")

    unique_name(req.args.name, (await project_names()))

    if req.dry_run:
        return None

    if glob.SCENE:
        if glob.SCENE.id != req.args.scene_id:
            raise Arcor2Exception("Another scene is opened.")

        if glob.SCENE.has_changes():
            glob.SCENE.modified = await storage.update_scene(glob.SCENE.scene)
    else:

        if req.args.scene_id not in {scene.id for scene in (await storage.get_scenes()).items}:
            raise Arcor2Exception("Unknown scene id.")

        await open_scene(req.args.scene_id)

    project.PREV_RESULTS.clear()
    glob.PROJECT = UpdateableCachedProject(
        common.Project(req.args.name, req.args.scene_id, desc=req.args.desc, has_logic=req.args.has_logic)
    )

    assert glob.SCENE

    asyncio.ensure_future(
        notif.broadcast_event(sevts.p.OpenProject(sevts.p.OpenProject.Data(glob.SCENE.scene, glob.PROJECT.project)))
    )
    return None


@scene_needed
@project_needed
async def close_project_cb(req: srpc.p.CloseProject.Request, ui: WsClient) -> None:

    can_modify_scene()

    assert glob.PROJECT

    if not req.args.force and glob.PROJECT.has_changes:
        raise Arcor2Exception("Project has unsaved changes.")

    if req.dry_run:
        return None

    await close_project()
    return None


def check_ap_parent(parent: Optional[str]) -> None:

    assert glob.SCENE
    assert glob.PROJECT

    if not parent:
        return

    if parent in glob.SCENE.object_ids:
        if glob.SCENE.object(parent).pose is None:
            raise Arcor2Exception("AP can't have object without pose as parent.")
    elif parent not in glob.PROJECT.action_points_ids:
        raise Arcor2Exception("AP has invalid parent ID (not an object or another AP).")


@scene_needed
@project_needed
async def add_action_point_cb(req: srpc.p.AddActionPoint.Request, ui: WsClient) -> None:

    assert glob.SCENE
    assert glob.PROJECT

    hlp.is_valid_identifier(req.args.name)
    unique_name(req.args.name, glob.PROJECT.action_points_names)
    check_ap_parent(req.args.parent)

    if req.dry_run:
        return None

    ap = glob.PROJECT.upsert_action_point(common.ActionPoint.uid(), req.args.name, req.args.position, req.args.parent)

    evt = sevts.p.ActionPointChanged(ap)
    evt.change_type = Event.Type.ADD
    asyncio.ensure_future(notif.broadcast_event(evt))
    return None


@scene_needed
@project_needed
async def remove_action_point_cb(req: srpc.p.RemoveActionPoint.Request, ui: WsClient) -> None:

    assert glob.PROJECT

    ap = glob.PROJECT.bare_action_point(req.args.id)

    for proj_ap in glob.PROJECT.action_points_with_parent:
        if proj_ap.parent == ap.id:
            raise Arcor2Exception(f"Can't remove parent of '{proj_ap.name}' AP.")

    ap_action_ids = glob.PROJECT.ap_action_ids(ap.id)

    # check if AP's actions aren't involved in logic
    # TODO 'force' param to remove logical connections?
    for logic in glob.PROJECT.logic:
        if (
            logic.start in ap_action_ids
            or logic.end in ap_action_ids
            or (logic.condition and logic.condition.parse_what().action_id in ap_action_ids)
        ):
            raise Arcor2Exception("Remove logic connections first.")

    for act in glob.PROJECT.actions:

        if act.id in ap_action_ids:
            continue

        for param in act.parameters:
            if param.type == common.ActionParameter.TypeEnum.LINK:
                parsed_link = param.parse_link()
                linking_action = glob.PROJECT.action(parsed_link.action_id)
                if parsed_link.action_id in ap_action_ids:
                    raise Arcor2Exception(f"Result of '{act.name}' is linked from '{linking_action.name}'.")

            if not param.is_value():
                continue

            for joints in glob.PROJECT.ap_joints(ap.id):
                if plugin_from_type_name(param.type).uses_robot_joints(glob.PROJECT, act.id, param.name, joints.id):
                    raise Arcor2Exception(f"Joints {joints.name} used in action {act.name} (parameter {param.name}).")

            for ori in glob.PROJECT.ap_orientations(ap.id):
                if plugin_from_type_name(param.type).uses_orientation(glob.PROJECT, act.id, param.name, ori.id):
                    raise Arcor2Exception(f"Orientation {ori.name} used in action {act.name} (parameter {param.name}).")

            # TODO some hypothetical parameter type could use just bare ActionPoint (its position)

    if req.dry_run:
        return None

    glob.PROJECT.remove_action_point(req.args.id)

    evt = sevts.p.ActionPointChanged(ap)
    evt.change_type = Event.Type.REMOVE
    asyncio.ensure_future(notif.broadcast_event(evt))
    return None


@scene_needed
@project_needed
async def copy_action_point_cb(req: srpc.p.CopyActionPoint.Request, ui: WsClient) -> None:

    assert glob.PROJECT

    def make_name_unique(orig_name: str, names: Set[str]) -> str:

        cnt = 1
        name = orig_name

        while name in names:
            name = f"{orig_name}_{cnt}"
            cnt += 1

        return name

    async def copy_action_point(
        orig_ap: common.BareActionPoint,
        new_parent_id: Optional[str] = None,
        position: Optional[common.Position] = None,
    ) -> None:

        assert glob.PROJECT

        ap = glob.PROJECT.upsert_action_point(
            common.ActionPoint.uid(),
            make_name_unique(f"{orig_ap.name}_copy", glob.PROJECT.action_points_names),
            orig_ap.position if position is None else position,
            orig_ap.parent if new_parent_id is None else new_parent_id,
        )

        ap_added_evt = sevts.p.ActionPointChanged(ap)
        ap_added_evt.change_type = Event.Type.ADD
        await notif.broadcast_event(ap_added_evt)

        for ori in glob.PROJECT.ap_orientations(orig_ap.id):
            new_ori = ori.copy()
            glob.PROJECT.upsert_orientation(ap.id, new_ori)

            ori_added_evt = sevts.p.OrientationChanged(new_ori)
            ori_added_evt.change_type = Event.Type.ADD
            ori_added_evt.parent_id = ap.id
            await notif.broadcast_event(ori_added_evt)

        for joints in glob.PROJECT.ap_joints(orig_ap.id):
            new_joints = joints.copy()
            glob.PROJECT.upsert_joints(ap.id, new_joints)

            joints_added_evt = sevts.p.JointsChanged(new_joints)
            joints_added_evt.change_type = Event.Type.ADD
            joints_added_evt.parent_id = ap.id
            await notif.broadcast_event(joints_added_evt)

        action_names = glob.PROJECT.action_names  # action name has to be globally unique
        for act in glob.PROJECT.ap_actions(orig_ap.id):
            new_act = act.copy()
            new_act.name = make_name_unique(f"{act.name}_copy", action_names)
            glob.PROJECT.upsert_action(ap.id, new_act)

            action_added_evt = sevts.p.ActionChanged(new_act)
            action_added_evt.change_type = Event.Type.ADD
            action_added_evt.parent_id = ap.id
            await notif.broadcast_event(action_added_evt)

        for child_ap in glob.PROJECT.action_points_with_parent:
            if child_ap.parent == orig_ap.id:
                await copy_action_point(child_ap, ap.id)

    original_ap = glob.PROJECT.bare_action_point(req.args.id)

    if req.dry_run:
        return

    asyncio.ensure_future(copy_action_point(original_ap, position=req.args.position))


@scene_needed
@project_needed
async def add_action_cb(req: srpc.p.AddAction.Request, ui: WsClient) -> None:

    assert glob.PROJECT
    assert glob.SCENE

    ap = glob.PROJECT.bare_action_point(req.args.action_point_id)

    unique_name(req.args.name, glob.PROJECT.action_names)

    new_action = common.Action(req.args.name, req.args.type, parameters=req.args.parameters, flows=req.args.flows)

    action_meta = find_object_action(glob.SCENE, new_action)

    updated_project = copy.deepcopy(glob.PROJECT)
    updated_project.upsert_action(req.args.action_point_id, new_action)

    check_flows(updated_project, new_action, action_meta)
    check_action_params(glob.SCENE, updated_project, new_action, action_meta)

    if req.dry_run:
        return None

    glob.PROJECT.upsert_action(ap.id, new_action)

    evt = sevts.p.ActionChanged(new_action)
    evt.change_type = Event.Type.ADD
    evt.parent_id = ap.id
    asyncio.ensure_future(notif.broadcast_event(evt))
    return None


@scene_needed
@project_needed
async def update_action_cb(req: srpc.p.UpdateAction.Request, ui: WsClient) -> None:

    assert glob.PROJECT
    assert glob.SCENE

    updated_project = copy.deepcopy(glob.PROJECT)

    updated_action = updated_project.action(req.args.action_id)

    if req.args.parameters is not None:
        updated_action.parameters = req.args.parameters
    if req.args.flows is not None:
        updated_action.flows = req.args.flows

    updated_action_meta = find_object_action(glob.SCENE, updated_action)

    check_flows(updated_project, updated_action, updated_action_meta)
    check_action_params(glob.SCENE, updated_project, updated_action, updated_action_meta)

    if req.dry_run:
        return None

    orig_action = glob.PROJECT.action(req.args.action_id)
    orig_action.parameters = updated_action.parameters
    glob.PROJECT.update_modified()

    evt = sevts.p.ActionChanged(updated_action)
    evt.change_type = Event.Type.UPDATE
    asyncio.ensure_future(notif.broadcast_event(evt))
    return None


def check_action_usage(action: common.Action) -> None:

    assert glob.PROJECT

    # check parameters
    for act in glob.PROJECT.actions:
        for param in act.parameters:
            if param.type == common.ActionParameter.TypeEnum.LINK:
                link = param.parse_link()
                if action.id == link.action_id:
                    raise Arcor2Exception(f"Action output used as parameter of {act.name}/{param.name}.")

    # check logic
    for log in glob.PROJECT.logic:

        if log.start == action.id or log.end == action.id:
            raise Arcor2Exception("Action used in logic.")

        if log.condition:
            action_id, _, _ = log.condition.what.split("/")

            if action_id == action.id:
                raise Arcor2Exception("Action used in condition.")


@scene_needed
@project_needed
async def remove_action_cb(req: srpc.p.RemoveAction.Request, ui: WsClient) -> None:

    assert glob.PROJECT
    assert glob.SCENE

    ap, action = glob.PROJECT.action_point_and_action(req.args.id)
    check_action_usage(action)

    if req.dry_run:
        return None

    glob.PROJECT.remove_action(req.args.id)
    project.remove_prev_result(action.id)

    evt = sevts.p.ActionChanged(action.bare)
    evt.change_type = Event.Type.REMOVE
    asyncio.ensure_future(notif.broadcast_event(evt))
    return None


def check_logic_item(parent: LogicContainer, logic_item: common.LogicItem) -> None:
    """Checks if newly added/updated ProjectLogicItem is ok.

    :param parent:
    :param logic_item:
    :return:
    """

    assert glob.SCENE

    action_ids = parent.action_ids()

    if logic_item.start == common.LogicItem.START and logic_item.end == common.LogicItem.END:
        raise Arcor2Exception("This does not make sense.")

    if logic_item.start != common.LogicItem.START:

        start_action_id, start_flow = logic_item.parse_start()

        if start_action_id == logic_item.end:
            raise Arcor2Exception("Start and end can't be the same.")

        if start_action_id not in action_ids:
            raise Arcor2Exception("Logic item has unknown start.")

        if start_flow != "default":
            raise Arcor2Exception("Only flow 'default' is supported so far.'")

    if logic_item.end != common.LogicItem.END:

        if logic_item.end not in action_ids:
            raise Arcor2Exception("Logic item has unknown end.")

    if logic_item.condition is not None:

        what = logic_item.condition.parse_what()
        action = parent.action(what.action_id)  # action that produced the result which we depend on here
        flow = action.flow(what.flow_name)
        try:
            flow.outputs[what.output_index]
        except IndexError:
            raise Arcor2Exception(f"Flow {flow.type} does not have output with index {what.output_index}.")

        action_meta = find_object_action(glob.SCENE, action)

        try:
            return_type = action_meta.returns[what.output_index]
        except IndexError:
            raise Arcor2Exception(f"Invalid output index {what.output_index} for action {action_meta.name}.")

        return_type_plugin = plugin_from_type_name(return_type)

        if not return_type_plugin.COUNTABLE:
            raise Arcor2Exception(f"Output of type {return_type} can't be branched.")

        # TODO for now there is only support for bool
        if return_type_plugin.type() != bool:
            raise Arcor2Exception("Unsupported condition type.")

        # check that condition value is ok, actual value is not interesting
        # TODO perform this check using plugin
        import json

        if not isinstance(json.loads(logic_item.condition.value), bool):
            raise Arcor2Exception("Invalid condition value.")

    for existing_item in parent.logic:

        if existing_item.id == logic_item.id:  # item is updated
            continue

        if logic_item.start == logic_item.START and existing_item.start == logic_item.START:
            raise Arcor2Exception("START already defined.")

        if logic_item.start == existing_item.start:

            if None in (logic_item.condition, existing_item.condition):
                raise Arcor2Exception("Two junctions has the same start action without condition.")

            # when there are more logical connections from A to B, their condition values must be different
            if logic_item.condition == existing_item.condition:
                raise Arcor2Exception("Two junctions with the same start should have different conditions.")

        if logic_item.end == existing_item.end:
            if logic_item.start == existing_item.start:
                raise Arcor2Exception("Junctions can't have the same start and end.")


@scene_needed
@project_needed
async def add_logic_item_cb(req: srpc.p.AddLogicItem.Request, ui: WsClient) -> None:

    assert glob.PROJECT
    assert glob.SCENE

    logic_item = common.LogicItem(req.args.start, req.args.end, req.args.condition)
    check_logic_item(glob.PROJECT, logic_item)

    if logic_item.start != logic_item.START:
        updated_project = copy.deepcopy(glob.PROJECT)
        updated_project.upsert_logic_item(logic_item)
        check_for_loops(updated_project, logic_item.parse_start().start_action_id)

    if req.dry_run:
        return

    glob.PROJECT.upsert_logic_item(logic_item)

    evt = sevts.p.LogicItemChanged(logic_item)
    evt.change_type = Event.Type.ADD
    asyncio.ensure_future(notif.broadcast_event(evt))
    return None


@scene_needed
@project_needed
async def update_logic_item_cb(req: srpc.p.UpdateLogicItem.Request, ui: WsClient) -> None:

    assert glob.PROJECT
    assert glob.SCENE

    updated_project = copy.deepcopy(glob.PROJECT)
    updated_logic_item = updated_project.logic_item(req.args.logic_item_id)

    updated_logic_item.start = req.args.start
    updated_logic_item.end = req.args.end
    updated_logic_item.condition = req.args.condition

    check_logic_item(updated_project, updated_logic_item)

    if updated_logic_item.start != updated_logic_item.START:
        check_for_loops(updated_project, updated_logic_item.parse_start().start_action_id)

    if req.dry_run:
        return

    glob.PROJECT.upsert_logic_item(updated_logic_item)

    evt = sevts.p.LogicItemChanged(updated_logic_item)
    evt.change_type = Event.Type.UPDATE
    asyncio.ensure_future(notif.broadcast_event(evt))
    return None


@scene_needed
@project_needed
async def remove_logic_item_cb(req: srpc.p.RemoveLogicItem.Request, ui: WsClient) -> None:

    assert glob.PROJECT
    assert glob.SCENE

    logic_item = glob.PROJECT.logic_item(req.args.logic_item_id)

    # TODO is it necessary to check something here?
    glob.PROJECT.remove_logic_item(req.args.logic_item_id)

    evt = sevts.p.LogicItemChanged(logic_item)
    evt.change_type = Event.Type.REMOVE
    asyncio.ensure_future(notif.broadcast_event(evt))
    return None


def check_constant(constant: common.ProjectConstant) -> None:

    assert glob.PROJECT

    hlp.is_valid_identifier(constant.name)

    for const in glob.PROJECT.constants:

        if constant.id == const.id:
            continue

        if constant.name == const.name:
            raise Arcor2Exception("Name has to be unique.")

    # TODO check using (constant?) plugin
    import json

    val = json.loads(constant.value)

    if not isinstance(val, (int, float, str, bool)):
        raise Arcor2Exception("Only basic types are supported so far.")


@scene_needed
@project_needed
async def add_constant_cb(req: srpc.p.AddConstant.Request, ui: WsClient) -> None:

    assert glob.PROJECT
    assert glob.SCENE

    const = common.ProjectConstant(req.args.name, req.args.type, req.args.value)
    check_constant(const)

    if req.dry_run:
        return

    glob.PROJECT.upsert_constant(const)

    evt = sevts.p.ProjectConstantChanged(const)
    evt.change_type = Event.Type.ADD
    asyncio.ensure_future(notif.broadcast_event(evt))
    return None


@scene_needed
@project_needed
async def update_constant_cb(req: srpc.p.UpdateConstant.Request, ui: WsClient) -> None:

    assert glob.PROJECT
    assert glob.SCENE

    const = glob.PROJECT.constant(req.args.constant_id)

    updated_constant = copy.deepcopy(const)

    if req.args.name is not None:
        updated_constant.name = req.args.name
    if req.args.value is not None:
        updated_constant.value = req.args.value

    check_constant(const)

    if req.dry_run:
        return

    glob.PROJECT.upsert_constant(updated_constant)

    evt = sevts.p.ProjectConstantChanged(const)
    evt.change_type = Event.Type.UPDATE
    asyncio.ensure_future(notif.broadcast_event(evt))
    return None


@scene_needed
@project_needed
async def remove_constant_cb(req: srpc.p.RemoveConstant.Request, ui: WsClient) -> None:

    assert glob.PROJECT
    assert glob.SCENE

    const = glob.PROJECT.constant(req.args.constant_id)

    # check for usage
    for act in glob.PROJECT.actions:
        for param in act.parameters:
            if param.type == common.ActionParameter.TypeEnum.CONSTANT and param.value == const.id:
                raise Arcor2Exception("Constant used as action parameter.")

    if req.dry_run:
        return

    glob.PROJECT.remove_constant(const.id)

    evt = sevts.p.ProjectConstantChanged(const)
    evt.change_type = Event.Type.REMOVE
    asyncio.ensure_future(notif.broadcast_event(evt))
    return None


@no_project
async def delete_project_cb(req: srpc.p.DeleteProject.Request, ui: WsClient) -> None:

    project = UpdateableCachedProject(await storage.get_project(req.args.id))
    await storage.delete_project(req.args.id)

    evt = sevts.p.ProjectChanged(project.bare)
    evt.change_type = Event.Type.REMOVE
    asyncio.ensure_future(notif.broadcast_event(evt))
    return None


async def rename_project_cb(req: srpc.p.RenameProject.Request, ui: WsClient) -> None:

    unique_name(req.args.new_name, (await project_names()))

    if req.dry_run:
        return None

    async with managed_project(req.args.project_id) as project:

        project.name = req.args.new_name
        project.update_modified()

        evt = sevts.p.ProjectChanged(project.bare)
        evt.change_type = Event.Type.UPDATE_BASE
        asyncio.ensure_future(notif.broadcast_event(evt))
    return None


async def copy_project_cb(req: srpc.p.CopyProject.Request, ui: WsClient) -> None:

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

    async with managed_project(req.args.project_id) as project:

        project.desc = req.args.new_description
        project.update_modified()

        evt = sevts.p.ProjectChanged(project.bare)
        evt.change_type = Event.Type.UPDATE_BASE
        asyncio.ensure_future(notif.broadcast_event(evt))
    return None


async def update_project_has_logic_cb(req: srpc.p.UpdateProjectHasLogic.Request, ui: WsClient) -> None:

    async with managed_project(req.args.project_id) as project:

        if project.has_logic and not req.args.new_has_logic:
            project.clear_logic()

            """
            TODO
            if glob.PROJECT and glob.PROJECT.id == req.args.project_id:
            ...send remove event for each logic item?
            """

        project.has_logic = req.args.new_has_logic
        project.update_modified()

        evt = sevts.p.ProjectChanged(project.bare)
        evt.change_type = Event.Type.UPDATE_BASE
        asyncio.ensure_future(notif.broadcast_event(evt))
    return None


@project_needed
async def rename_action_point_joints_cb(req: srpc.p.RenameActionPointJoints.Request, ui: WsClient) -> None:

    assert glob.PROJECT

    ap, joints = glob.PROJECT.ap_and_joints(req.args.joints_id)
    hlp.is_valid_identifier(req.args.new_name)
    unique_name(req.args.new_name, glob.PROJECT.ap_joint_names(ap.id))

    if req.dry_run:
        return None

    joints.name = req.args.new_name
    glob.PROJECT.update_modified()

    evt = sevts.p.JointsChanged(joints)
    evt.change_type = Event.Type.UPDATE_BASE
    asyncio.ensure_future(notif.broadcast_event(evt))

    return None


@project_needed
async def rename_action_point_orientation_cb(req: srpc.p.RenameActionPointOrientation.Request, ui: WsClient) -> None:

    assert glob.PROJECT

    ap, ori = glob.PROJECT.bare_ap_and_orientation(req.args.orientation_id)
    hlp.is_valid_identifier(req.args.new_name)
    unique_name(req.args.new_name, glob.PROJECT.ap_orientation_names(ap.id))

    if req.dry_run:
        return None

    ori.name = req.args.new_name
    glob.PROJECT.update_modified()

    evt = sevts.p.OrientationChanged(ori)
    evt.change_type = Event.Type.UPDATE_BASE
    asyncio.ensure_future(notif.broadcast_event(evt))

    return None


@project_needed
async def rename_action_cb(req: srpc.p.RenameAction.Request, ui: WsClient) -> None:

    assert glob.PROJECT

    unique_name(req.args.new_name, glob.PROJECT.action_names)

    if req.dry_run:
        return None

    act = glob.PROJECT.action(req.args.action_id)
    act.name = req.args.new_name

    glob.PROJECT.update_modified()

    evt = sevts.p.ActionChanged(act)
    evt.change_type = Event.Type.UPDATE_BASE
    asyncio.ensure_future(notif.broadcast_event(evt))

    return None
