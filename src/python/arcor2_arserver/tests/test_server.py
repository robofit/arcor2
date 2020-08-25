import logging
import os
import subprocess as sp
import tempfile
from typing import Iterator, Tuple, Type, TypeVar

import pytest  # type: ignore

from arcor2.clients import persistent_storage
from arcor2.data import common
from arcor2.data import events as arcor2_events
from arcor2.data.events import Event, EventType
from arcor2.data.rpc.common import IdArgs
from arcor2.object_types.abstract import Generic, GenericWithPose
from arcor2.object_types.time_actions import TimeActions
from arcor2_arserver_data import events, objects, rpc
from arcor2_arserver_data.client import ARServer, uid
from arcor2_execution_data import events as eevents
from arcor2_execution_data import rpc as erpc
from arcor2_mocks import PROJECT_PORT, SCENE_PORT

persistent_storage.URL = f"http://0.0.0.0:{PROJECT_PORT}"

LOGGER = logging.getLogger(__name__)


def log_proc_output(out: Tuple[bytes, bytes]) -> None:

    for line in out[0].decode().splitlines():
        LOGGER.debug(line)


def finish_processes(processes) -> None:

    for proc in processes:
        proc.terminate()
        proc.wait()
        log_proc_output(proc.communicate())


@pytest.fixture()
def start_processes() -> Iterator[None]:

    with tempfile.TemporaryDirectory() as tmp_dir:

        my_env = os.environ.copy()
        my_env["ARCOR2_DATA_PATH"] = os.path.join(tmp_dir, "data")
        my_env["ARCOR2_PERSISTENT_STORAGE_URL"] = f"http://0.0.0.0:{PROJECT_PORT}"
        my_env["ARCOR2_SCENE_SERVICE_URL"] = f"http://0.0.0.0:{SCENE_PORT}"
        my_env["ARCOR2_PROJECT_PATH"] = os.path.join(tmp_dir, "packages")

        processes = []

        for cmd in ("arcor2_project_mock", "arcor2_scene_mock", "arcor2_execution", "arcor2_build"):
            processes.append(sp.Popen(cmd, env=my_env, stdout=sp.PIPE, stderr=sp.STDOUT))

        # it may take some time for project service to come up so give it some time
        for _ in range(3):
            upload = sp.Popen("arcor2_upload_builtin_objects", env=my_env, stdout=sp.PIPE, stderr=sp.STDOUT)
            ret = upload.communicate()
            if upload.returncode == 0:
                log_proc_output(ret)
                break
        else:
            raise Exception("Failed to upload objects.")

        processes.append(sp.Popen("arcor2_server", env=my_env, stdout=sp.PIPE, stderr=sp.STDOUT))

        yield None

        finish_processes(processes)


WS_CONNECTION_STR = "ws://0.0.0.0:6789"


@pytest.fixture()
def ars() -> Iterator[ARServer]:
    with ARServer(WS_CONNECTION_STR, timeout=10) as ws:
        yield ws


E = TypeVar("E", bound=Event)


def event(ars: ARServer, evt_type: Type[E]) -> E:

    evt = ars.get_event()
    assert isinstance(evt, evt_type)
    assert evt.event == evt_type.event  # type: ignore  # TODO investigate why mypy complains here
    return evt


def wait_for_event(ars: ARServer, evt_type: Type[E]) -> E:

    evt = ars.get_event(drop_everything_until=evt_type)
    assert isinstance(evt, evt_type)
    assert evt.event == evt_type.event  # type: ignore  # TODO investigate why mypy complains here
    return evt


@pytest.fixture()
def scene(ars: ARServer) -> common.Scene:

    assert isinstance(ars.get_event(), events.c.ShowMainScreenEvent)

    test = "Test scene"

    assert ars.call_rpc(
        rpc.s.NewSceneRequest(uid(), rpc.s.NewSceneRequestArgs(test, test)), rpc.s.NewSceneResponse
    ).result

    scene_evt = event(ars, events.s.OpenScene)
    assert scene_evt.data

    test_type = "TestType"

    assert ars.call_rpc(
        rpc.o.NewObjectTypeRequest(uid(), objects.ObjectTypeMeta(test_type, base=Generic.__name__)),
        rpc.o.NewObjectTypeResponse,
    ).result

    tt_evt = event(ars, events.o.ChangedObjectTypesEvent)

    assert len(tt_evt.data) == 1
    assert not tt_evt.data[0].has_pose
    assert tt_evt.data[0].type == test_type
    assert tt_evt.data[0].base == Generic.__name__

    assert ars.call_rpc(
        rpc.s.AddObjectToSceneRequest(uid(), rpc.s.AddObjectToSceneRequestArgs("test_type", test_type)),
        rpc.s.AddObjectToSceneResponse,
    ).result

    event(ars, events.s.SceneObjectChanged)

    test_type_with_pose = "TestTypeWithPose"

    assert ars.call_rpc(
        rpc.o.NewObjectTypeRequest(uid(), objects.ObjectTypeMeta(test_type_with_pose, base=GenericWithPose.__name__)),
        rpc.o.NewObjectTypeResponse,
    ).result

    ttwp_evt = event(ars, events.o.ChangedObjectTypesEvent)
    assert len(ttwp_evt.data) == 1
    assert ttwp_evt.data[0].has_pose
    assert ttwp_evt.data[0].type == test_type_with_pose
    assert ttwp_evt.data[0].base == GenericWithPose.__name__

    assert ars.call_rpc(
        rpc.s.AddObjectToSceneRequest(uid(), rpc.s.AddObjectToSceneRequestArgs("test_type_with_pose", test_type)),
        rpc.s.AddObjectToSceneResponse,
    ).result

    event(ars, events.s.SceneObjectChanged)

    assert ars.call_rpc(rpc.s.SaveSceneRequest(uid()), rpc.s.SaveSceneResponse).result
    event(ars, events.s.SceneSaved)
    assert ars.call_rpc(rpc.s.CloseSceneRequest(uid()), rpc.s.CloseSceneResponse).result
    event(ars, events.s.SceneClosed)
    event(ars, events.c.ShowMainScreenEvent)

    return scene_evt.data.scene


@pytest.mark.skip(reason="Integration tests are temporarily disabled.")
def test_scene_basic_rpcs(start_processes: None, ars: ARServer) -> None:

    test = "Test"

    # initial event
    show_main_screen_event = event(ars, events.c.ShowMainScreenEvent)
    assert show_main_screen_event.data
    assert show_main_screen_event.data.what == events.c.ShowMainScreenData.WhatEnum.ScenesList

    # first, there are no scenes
    scenes = ars.call_rpc(rpc.s.ListScenesRequest(uid()), rpc.s.ListScenesResponse)
    assert scenes.result
    assert not scenes.data

    assert ars.call_rpc(
        rpc.s.NewSceneRequest(uid(), rpc.s.NewSceneRequestArgs(test, test)), rpc.s.NewSceneResponse
    ).result

    open_scene_event = event(ars, events.s.OpenScene)
    assert open_scene_event.parent_id is None
    assert open_scene_event.change_type is None
    assert open_scene_event.data
    assert open_scene_event.data.scene.id
    scene_id = open_scene_event.data.scene.id
    assert open_scene_event.data.scene.name == test
    assert open_scene_event.data.scene.desc == test
    assert not open_scene_event.data.scene.objects

    # attempt to create a new scene while scene is open should fail
    assert not ars.call_rpc(
        rpc.s.NewSceneRequest(uid(), rpc.s.NewSceneRequestArgs(test, test)), rpc.s.NewSceneResponse
    ).result

    assert ars.call_rpc(rpc.s.SaveSceneRequest(uid()), rpc.s.SaveSceneResponse).result

    event(ars, events.s.SceneSaved)

    assert ars.call_rpc(rpc.s.CloseSceneRequest(uid()), rpc.s.CloseSceneResponse).result

    event(ars, events.s.SceneClosed)

    show_main_screen_event_2 = event(ars, events.c.ShowMainScreenEvent)
    assert show_main_screen_event_2.data
    assert show_main_screen_event_2.data.what == events.c.ShowMainScreenData.WhatEnum.ScenesList
    assert show_main_screen_event_2.data.highlight == scene_id

    # attempt to open non-existent scene
    assert not ars.call_rpc(
        rpc.s.OpenSceneRequest(uid(), IdArgs("some-random-nonsense")), rpc.s.OpenSceneResponse
    ).result

    list_of_scenes = ars.call_rpc(rpc.s.ListScenesRequest(uid()), rpc.s.ListScenesResponse)
    assert list_of_scenes.result
    assert len(list_of_scenes.data) == 1
    assert list_of_scenes.data[0].id == scene_id

    # open previously saved scene
    assert ars.call_rpc(rpc.s.OpenSceneRequest(uid(), IdArgs(scene_id)), rpc.s.OpenSceneResponse).result

    open_scene_event_2 = event(ars, events.s.OpenScene)
    assert open_scene_event_2.data
    assert open_scene_event_2.data.scene.id == scene_id

    assert ars.call_rpc(rpc.s.CloseSceneRequest(uid()), rpc.s.CloseSceneResponse).result
    event(ars, events.s.SceneClosed)

    show_main_screen_event_3 = event(ars, events.c.ShowMainScreenEvent)
    assert show_main_screen_event_3.data
    assert show_main_screen_event_3.data.what == events.c.ShowMainScreenData.WhatEnum.ScenesList
    assert show_main_screen_event_3.data.highlight == scene_id

    with ARServer(WS_CONNECTION_STR) as ars_2:

        smse = event(ars_2, events.c.ShowMainScreenEvent)
        assert smse.data
        assert smse.data.what == events.c.ShowMainScreenData.WhatEnum.ScenesList
        assert smse.data.highlight is None

    assert ars.call_rpc(rpc.s.DeleteSceneRequest(uid(), IdArgs(scene_id)), rpc.s.DeleteSceneResponse).result

    scene_changed_evt = event(ars, events.s.SceneChanged)
    assert scene_changed_evt.data
    assert scene_changed_evt.data.id == scene_id
    assert scene_changed_evt.change_type == EventType.REMOVE

    list_of_scenes_2 = ars.call_rpc(rpc.s.ListScenesRequest(uid()), rpc.s.ListScenesResponse)
    assert list_of_scenes_2.result
    assert not list_of_scenes_2.data


def save_project(ars: ARServer) -> None:

    assert ars.call_rpc(rpc.p.SaveProjectRequest(uid()), rpc.p.SaveProjectResponse).result
    event(ars, events.p.ProjectSaved)


def close_project(ars: ARServer) -> None:

    assert ars.call_rpc(rpc.p.CloseProjectRequest(uid()), rpc.p.CloseProjectResponse).result
    event(ars, events.p.ProjectClosed)


@pytest.mark.skip(reason="Integration tests are temporarily disabled.")
def test_project_basic_rpcs(start_processes: None, ars: ARServer, scene: common.Scene) -> None:

    # first, there are no projects
    projects = ars.call_rpc(rpc.p.ListProjectsRequest(uid()), rpc.p.ListProjectsResponse)
    assert projects.result
    assert not projects.data

    project_name = "Test project"

    # attempt to use non-existent scene_id
    assert not ars.call_rpc(
        rpc.p.NewProjectRequest(uid(), rpc.p.NewProjectRequestArgs("some non-sense string", project_name)),
        rpc.p.NewProjectResponse,
    ).result

    # attempt to open non-existent project
    assert not ars.call_rpc(
        rpc.p.OpenProjectRequest(uid(), IdArgs("some-random-nonsense")), rpc.p.OpenProjectResponse
    ).result

    # correct scene_id
    assert ars.call_rpc(
        rpc.p.NewProjectRequest(uid(), rpc.p.NewProjectRequestArgs(scene.id, project_name)), rpc.p.NewProjectResponse
    ).result

    open_project_evt = event(ars, events.p.OpenProject)

    assert open_project_evt.data
    assert open_project_evt.change_type is None
    assert open_project_evt.parent_id is None
    assert open_project_evt.data.scene.id == scene.id
    project_id = open_project_evt.data.project.id

    assert open_project_evt.data.project.name == project_name
    assert not open_project_evt.data.project.action_points
    assert not open_project_evt.data.project.constants
    assert not open_project_evt.data.project.functions
    assert not open_project_evt.data.project.logic

    # attempt to create project while another project is opened
    assert not ars.call_rpc(
        rpc.p.NewProjectRequest(uid(), rpc.p.NewProjectRequestArgs("some non-sense string", "blah")),
        rpc.p.NewProjectResponse,
    ).result

    save_project(ars)
    close_project(ars)

    show_main_screen_event = event(ars, events.c.ShowMainScreenEvent)
    assert show_main_screen_event.data
    assert show_main_screen_event.data.what == events.c.ShowMainScreenData.WhatEnum.ProjectsList
    assert show_main_screen_event.data.highlight == project_id

    list_of_projects = ars.call_rpc(rpc.p.ListProjectsRequest(uid()), rpc.p.ListProjectsResponse)
    assert list_of_projects.result
    assert len(list_of_projects.data) == 1
    assert list_of_projects.data[0].id == project_id

    with ARServer(WS_CONNECTION_STR) as ars_2:

        smse = event(ars_2, events.c.ShowMainScreenEvent)
        assert smse.data
        assert smse.data.what == events.c.ShowMainScreenData.WhatEnum.ProjectsList
        assert smse.data.highlight is None

    # it should not be possible to delete scene used by a project
    assert not ars.call_rpc(rpc.s.DeleteSceneRequest(uid(), IdArgs(scene.id)), rpc.s.DeleteSceneResponse).result

    assert ars.call_rpc(rpc.p.DeleteProjectRequest(uid(), IdArgs(project_id)), rpc.p.DeleteProjectResponse).result

    project_changed_evt = event(ars, events.p.ProjectChanged)
    assert project_changed_evt.data
    assert project_changed_evt.data.id == project_id
    assert project_changed_evt.change_type == EventType.REMOVE

    assert ars.call_rpc(rpc.s.DeleteSceneRequest(uid(), IdArgs(scene.id)), rpc.s.DeleteSceneResponse).result

    scene_changed_evt = event(ars, events.s.SceneChanged)
    assert scene_changed_evt.data
    assert scene_changed_evt.data.id == scene.id
    assert scene_changed_evt.change_type == EventType.REMOVE

    list_of_projects_2 = ars.call_rpc(rpc.p.ListProjectsRequest(uid()), rpc.p.ListProjectsResponse)
    assert list_of_projects_2.result
    assert not list_of_projects_2.data


@pytest.mark.skip(reason="Not finished yet.")
def test_project_ap_rpcs(start_processes: None, ars: ARServer, scene: common.Scene) -> None:

    assert ars.call_rpc(
        rpc.p.NewProjectRequest(uid(), rpc.p.NewProjectRequestArgs(scene.id, "Project name")), rpc.p.NewProjectResponse
    ).result

    event(ars, events.p.OpenProject)

    # TODO add object-AP, global AP, etc.


def add_logic_item(ars: ARServer, start: str, end: str) -> common.LogicItem:

    assert ars.call_rpc(
        rpc.p.AddLogicItemRequest(uid(), rpc.p.AddLogicItemArgs(start, end)), rpc.p.AddLogicItemResponse
    ).result

    evt = event(ars, events.p.LogicItemChanged)
    assert evt.data
    return evt.data


@pytest.mark.skip(reason="Integration tests are temporarily disabled.")
def test_run_simple_project(start_processes: None, ars: ARServer) -> None:

    event(ars, events.c.ShowMainScreenEvent)

    assert ars.call_rpc(
        rpc.s.NewSceneRequest(uid(), rpc.s.NewSceneRequestArgs("Test scene")), rpc.s.NewSceneResponse
    ).result

    scene_data = event(ars, events.s.OpenScene).data
    assert scene_data
    scene = scene_data.scene

    assert ars.call_rpc(
        rpc.s.AddObjectToSceneRequest(uid(), rpc.s.AddObjectToSceneRequestArgs("time_actions", TimeActions.__name__)),
        rpc.s.AddObjectToSceneResponse,
    ).result

    obj = event(ars, events.s.SceneObjectChanged).data
    assert obj

    assert ars.call_rpc(
        rpc.p.NewProjectRequest(uid(), rpc.p.NewProjectRequestArgs(scene.id, "Project name")), rpc.p.NewProjectResponse
    ).result

    proj = event(ars, events.p.OpenProject).data
    assert proj

    assert ars.call_rpc(
        rpc.p.AddActionPointRequest(uid(), rpc.p.AddActionPointArgs("ap1", common.Position())),
        rpc.p.AddActionPointResponse,
    ).result

    ap = event(ars, events.p.ActionPointChanged).data
    assert ap is not None

    assert ars.call_rpc(
        rpc.p.AddActionRequest(
            uid(),
            rpc.p.AddActionRequestArgs(
                ap.id,
                "test_action",
                f"{obj.id}/{TimeActions.sleep.__name__}",
                [common.ActionParameter("seconds", "double", "0.5")],
                [common.Flow()],
            ),
        ),
        rpc.p.AddActionResponse,
    ).result

    action = event(ars, events.p.ActionChanged).data
    assert action is not None

    add_logic_item(ars, common.LogicItem.START, action.id)
    add_logic_item(ars, action.id, common.LogicItem.END)

    save_project(ars)

    LOGGER.debug(persistent_storage.get_project(proj.project.id))

    # TODO test also temporary package

    close_project(ars)

    event(ars, events.c.ShowMainScreenEvent)

    assert ars.call_rpc(
        rpc.b.BuildProjectRequest(uid(), rpc.b.BuildProjectArgs(proj.project.id, "Package name")),
        rpc.b.BuildProjectResponse,
    ).result

    package = event(ars, eevents.PackageChanged).data
    assert package is not None

    assert ars.call_rpc(erpc.RunPackageRequest(uid(), erpc.RunPackageArgs(package.id)), erpc.RunPackageResponse).result

    ps = event(ars, arcor2_events.PackageStateEvent).data
    assert ps
    assert ps.package_id == package.id
    assert ps.state == ps.state.RUNNING

    pi = event(ars, arcor2_events.PackageInfoEvent).data
    assert pi
    assert pi.package_id == package.id

    act_in = event(ars, arcor2_events.CurrentActionEvent).data
    assert act_in
    assert act_in.action_id == action.id
    # assert len(act_in.args) == 1
    # assert act_in.args[0].name == "seconds"
    # assert act_in.args[0].type == "double"
    # assert act_in.args[0].value == "0.1"

    act_state_before = event(ars, arcor2_events.ActionStateEvent).data
    assert act_state_before
    assert act_state_before.method == TimeActions.sleep.__name__
    assert act_state_before.where == act_state_before.where.BEFORE

    act_state_after = event(ars, arcor2_events.ActionStateEvent).data
    assert act_state_after
    assert act_state_after.method == TimeActions.sleep.__name__
    assert act_state_after.where == act_state_after.where.AFTER

    # TODO pause, resume

    assert ars.call_rpc(erpc.StopPackageRequest(uid()), erpc.StopPackageResponse).result

    ps2 = wait_for_event(ars, arcor2_events.PackageStateEvent).data
    assert ps2
    assert ps2.package_id == package.id
    assert ps2.state == ps.state.STOPPED

    show_main_screen_event = event(ars, events.c.ShowMainScreenEvent)
    assert show_main_screen_event.data
    assert show_main_screen_event.data.what == events.c.ShowMainScreenData.WhatEnum.PackagesList
    assert show_main_screen_event.data.highlight == package.id
