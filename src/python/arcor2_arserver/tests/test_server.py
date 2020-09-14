import inspect
import logging
import os
import subprocess as sp
import tempfile
from typing import Dict, Iterator, Tuple, Type, TypeVar

import pytest  # type: ignore

from arcor2.clients import persistent_storage
from arcor2.data import common
from arcor2.data import events as arcor2_events
from arcor2.data.events import Event
from arcor2.data.rpc.common import IdArgs
from arcor2.object_types.abstract import Generic, GenericWithPose
from arcor2.object_types.time_actions import TimeActions
from arcor2_arserver_data import events, objects, rpc
from arcor2_arserver_data.client import ARServer, uid
from arcor2_execution_data import EVENTS as EXE_EVENTS
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

        for cmd in (
            "./src.python.arcor2_mocks.scripts/mock_project.pex",
            "src.python.arcor2_mocks.scripts/mock_scene.pex",
            "./src.python.arcor2_execution.scripts/execution.pex",
            "./src.python.arcor2_build.scripts/build.pex",
        ):
            processes.append(sp.Popen(cmd, env=my_env, stdout=sp.PIPE, stderr=sp.STDOUT))

        # it may take some time for project service to come up so give it some time
        for _ in range(3):
            upload = sp.Popen(
                "./src.python.arcor2.scripts/upload_builtin_objects.pex", env=my_env, stdout=sp.PIPE, stderr=sp.STDOUT
            )
            ret = upload.communicate()
            if upload.returncode == 0:
                log_proc_output(ret)
                break
        else:
            raise Exception("Failed to upload objects.")

        processes.append(
            sp.Popen("./src.python.arcor2_arserver.scripts/arserver.pex", env=my_env, stdout=sp.PIPE, stderr=sp.STDOUT)
        )

        yield None

        finish_processes(processes)


WS_CONNECTION_STR = "ws://0.0.0.0:6789"

# TODO refactor this into _data packages
event_mapping: Dict[str, Type[Event]] = {evt.__name__: evt for evt in EXE_EVENTS}

modules = []

for _, mod in inspect.getmembers(events, inspect.ismodule):
    modules.append(mod)

for mod in modules:
    for _, cls in inspect.getmembers(mod, inspect.isclass):
        if issubclass(cls, Event):
            event_mapping[cls.__name__] = cls


@pytest.fixture()
def ars() -> Iterator[ARServer]:

    with ARServer(WS_CONNECTION_STR, timeout=10, event_mapping=event_mapping) as ws:
        yield ws


E = TypeVar("E", bound=Event)


def event(ars: ARServer, evt_type: Type[E]) -> E:

    evt = ars.get_event()
    assert isinstance(evt, evt_type)
    assert evt.event == evt_type.__name__  # type: ignore # TODO figure out why mypy complains
    return evt


def wait_for_event(ars: ARServer, evt_type: Type[E]) -> E:

    evt = ars.get_event(drop_everything_until=evt_type)
    assert isinstance(evt, evt_type)
    assert evt.event == evt_type.__name__  # type: ignore # TODO figure out why mypy complains
    return evt


@pytest.fixture()
def scene(ars: ARServer) -> common.Scene:

    assert isinstance(ars.get_event(), events.c.ShowMainScreen)

    test = "Test scene"

    assert ars.call_rpc(
        rpc.s.NewScene.Request(uid(), rpc.s.NewScene.Request.Args(test, test)), rpc.s.NewScene.Response
    ).result

    scene_evt = event(ars, events.s.OpenScene)
    assert scene_evt.data

    test_type = "TestType"

    assert ars.call_rpc(
        rpc.o.NewObjectType.Request(uid(), objects.ObjectTypeMeta(test_type, base=Generic.__name__)),
        rpc.o.NewObjectType.Response,
    ).result

    tt_evt = event(ars, events.o.ChangedObjectTypes)

    assert len(tt_evt.data) == 1
    assert not tt_evt.data[0].has_pose
    assert tt_evt.data[0].type == test_type
    assert tt_evt.data[0].base == Generic.__name__

    assert ars.call_rpc(
        rpc.s.AddObjectToScene.Request(uid(), rpc.s.AddObjectToScene.Request.Args("test_type", test_type)),
        rpc.s.AddObjectToScene.Response,
    ).result

    event(ars, events.s.SceneObjectChanged)

    test_type_with_pose = "TestTypeWithPose"

    assert ars.call_rpc(
        rpc.o.NewObjectType.Request(uid(), objects.ObjectTypeMeta(test_type_with_pose, base=GenericWithPose.__name__)),
        rpc.o.NewObjectType.Response,
    ).result

    ttwp_evt = event(ars, events.o.ChangedObjectTypes)
    assert len(ttwp_evt.data) == 1
    assert ttwp_evt.data[0].has_pose
    assert ttwp_evt.data[0].type == test_type_with_pose
    assert ttwp_evt.data[0].base == GenericWithPose.__name__

    assert ars.call_rpc(
        rpc.s.AddObjectToScene.Request(uid(), rpc.s.AddObjectToScene.Request.Args("test_type_with_pose", test_type)),
        rpc.s.AddObjectToScene.Response,
    ).result

    event(ars, events.s.SceneObjectChanged)

    assert ars.call_rpc(rpc.s.SaveScene.Request(uid()), rpc.s.SaveScene.Response).result
    event(ars, events.s.SceneSaved)
    assert ars.call_rpc(rpc.s.CloseScene.Request(uid()), rpc.s.CloseScene.Response).result
    event(ars, events.s.SceneClosed)
    event(ars, events.c.ShowMainScreen)

    return scene_evt.data.scene


def test_scene_basic_rpcs(start_processes: None, ars: ARServer) -> None:

    test = "Test"

    # initial event
    show_main_screen_event = event(ars, events.c.ShowMainScreen)
    assert show_main_screen_event.data
    assert show_main_screen_event.data.what == events.c.ShowMainScreen.Data.WhatEnum.ScenesList

    # first, there are no scenes
    scenes = ars.call_rpc(rpc.s.ListScenes.Request(uid()), rpc.s.ListScenes.Response)
    assert scenes.result
    assert not scenes.data

    assert ars.call_rpc(
        rpc.s.NewScene.Request(uid(), rpc.s.NewScene.Request.Args(test, test)), rpc.s.NewScene.Response
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
        rpc.s.NewScene.Request(uid(), rpc.s.NewScene.Request.Args(test, test)), rpc.s.NewScene.Response
    ).result

    assert ars.call_rpc(rpc.s.SaveScene.Request(uid()), rpc.s.SaveScene.Response).result

    event(ars, events.s.SceneSaved)

    assert ars.call_rpc(rpc.s.CloseScene.Request(uid()), rpc.s.CloseScene.Response).result

    event(ars, events.s.SceneClosed)

    show_main_screen_event_2 = event(ars, events.c.ShowMainScreen)
    assert show_main_screen_event_2.data
    assert show_main_screen_event_2.data.what == events.c.ShowMainScreen.Data.WhatEnum.ScenesList
    assert show_main_screen_event_2.data.highlight == scene_id

    # attempt to open non-existent scene
    assert not ars.call_rpc(
        rpc.s.OpenScene.Request(uid(), IdArgs("some-random-nonsense")), rpc.s.OpenScene.Response
    ).result

    list_of_scenes = ars.call_rpc(rpc.s.ListScenes.Request(uid()), rpc.s.ListScenes.Response)
    assert list_of_scenes.result
    assert list_of_scenes.data
    assert len(list_of_scenes.data) == 1
    assert list_of_scenes.data[0].id == scene_id

    # open previously saved scene
    assert ars.call_rpc(rpc.s.OpenScene.Request(uid(), IdArgs(scene_id)), rpc.s.OpenScene.Response).result

    open_scene_event_2 = event(ars, events.s.OpenScene)
    assert open_scene_event_2.data
    assert open_scene_event_2.data.scene.id == scene_id

    assert ars.call_rpc(rpc.s.CloseScene.Request(uid()), rpc.s.CloseScene.Response).result
    event(ars, events.s.SceneClosed)

    show_main_screen_event_3 = event(ars, events.c.ShowMainScreen)
    assert show_main_screen_event_3.data
    assert show_main_screen_event_3.data.what == events.c.ShowMainScreen.Data.WhatEnum.ScenesList
    assert show_main_screen_event_3.data.highlight == scene_id

    with ARServer(WS_CONNECTION_STR, timeout=10, event_mapping=event_mapping) as ars_2:

        smse = event(ars_2, events.c.ShowMainScreen)
        assert smse.data
        assert smse.data.what == events.c.ShowMainScreen.Data.WhatEnum.ScenesList
        assert smse.data.highlight is None

    assert ars.call_rpc(rpc.s.DeleteScene.Request(uid(), IdArgs(scene_id)), rpc.s.DeleteScene.Response).result

    scene_changed_evt = event(ars, events.s.SceneChanged)
    assert scene_changed_evt.data
    assert scene_changed_evt.data.id == scene_id
    assert scene_changed_evt.change_type == Event.Type.REMOVE

    list_of_scenes_2 = ars.call_rpc(rpc.s.ListScenes.Request(uid()), rpc.s.ListScenes.Response)
    assert list_of_scenes_2.result
    assert not list_of_scenes_2.data


def save_project(ars: ARServer) -> None:

    assert ars.call_rpc(rpc.p.SaveProject.Request(uid()), rpc.p.SaveProject.Response).result
    event(ars, events.p.ProjectSaved)


def close_project(ars: ARServer) -> None:

    assert ars.call_rpc(rpc.p.CloseProject.Request(uid()), rpc.p.CloseProject.Response).result
    event(ars, events.p.ProjectClosed)


def test_project_basic_rpcs(start_processes: None, ars: ARServer, scene: common.Scene) -> None:

    # first, there are no projects
    projects = ars.call_rpc(rpc.p.ListProjects.Request(uid()), rpc.p.ListProjects.Response)
    assert projects.result
    assert not projects.data

    project_name = "Test project"

    # attempt to use non-existent scene_id
    assert not ars.call_rpc(
        rpc.p.NewProject.Request(uid(), rpc.p.NewProject.Request.Args("some non-sense string", project_name)),
        rpc.p.NewProject.Response,
    ).result

    # attempt to open non-existent project
    assert not ars.call_rpc(
        rpc.p.OpenProject.Request(uid(), IdArgs("some-random-nonsense")), rpc.p.OpenProject.Response
    ).result

    # correct scene_id
    assert ars.call_rpc(
        rpc.p.NewProject.Request(uid(), rpc.p.NewProject.Request.Args(scene.id, project_name)),
        rpc.p.NewProject.Response,
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
        rpc.p.NewProject.Request(uid(), rpc.p.NewProject.Request.Args("some non-sense string", "blah")),
        rpc.p.NewProject.Response,
    ).result

    save_project(ars)
    close_project(ars)

    show_main_screen_event = event(ars, events.c.ShowMainScreen)
    assert show_main_screen_event.data
    assert show_main_screen_event.data.what == events.c.ShowMainScreen.Data.WhatEnum.ProjectsList
    assert show_main_screen_event.data.highlight == project_id

    list_of_projects = ars.call_rpc(rpc.p.ListProjects.Request(uid()), rpc.p.ListProjects.Response)
    assert list_of_projects.result
    assert list_of_projects.data
    assert len(list_of_projects.data) == 1
    assert list_of_projects.data[0].id == project_id

    with ARServer(WS_CONNECTION_STR, timeout=10, event_mapping=event_mapping) as ars_2:

        smse = event(ars_2, events.c.ShowMainScreen)
        assert smse.data
        assert smse.data.what == events.c.ShowMainScreen.Data.WhatEnum.ProjectsList
        assert smse.data.highlight is None

    # it should not be possible to delete scene used by a project
    assert not ars.call_rpc(rpc.s.DeleteScene.Request(uid(), IdArgs(scene.id)), rpc.s.DeleteScene.Response).result

    assert ars.call_rpc(rpc.p.DeleteProject.Request(uid(), IdArgs(project_id)), rpc.p.DeleteProject.Response).result

    project_changed_evt = event(ars, events.p.ProjectChanged)
    assert project_changed_evt.data
    assert project_changed_evt.data.id == project_id
    assert project_changed_evt.change_type == Event.Type.REMOVE

    assert ars.call_rpc(rpc.s.DeleteScene.Request(uid(), IdArgs(scene.id)), rpc.s.DeleteScene.Response).result

    scene_changed_evt = event(ars, events.s.SceneChanged)
    assert scene_changed_evt.data
    assert scene_changed_evt.data.id == scene.id
    assert scene_changed_evt.change_type == Event.Type.REMOVE

    list_of_projects_2 = ars.call_rpc(rpc.p.ListProjects.Request(uid()), rpc.p.ListProjects.Response)
    assert list_of_projects_2.result
    assert not list_of_projects_2.data


@pytest.mark.skip(reason="Not finished yet.")
def test_project_ap_rpcs(start_processes: None, ars: ARServer, scene: common.Scene) -> None:

    assert ars.call_rpc(
        rpc.p.NewProject.Request(uid(), rpc.p.NewProject.Request.Args(scene.id, "Project name")),
        rpc.p.NewProject.Response,
    ).result

    event(ars, events.p.OpenProject)

    # TODO add object-AP, global AP, etc.


def add_logic_item(ars: ARServer, start: str, end: str) -> common.LogicItem:

    assert ars.call_rpc(
        rpc.p.AddLogicItem.Request(uid(), rpc.p.AddLogicItem.Request.Args(start, end)), rpc.p.AddLogicItem.Response
    ).result

    evt = event(ars, events.p.LogicItemChanged)
    assert evt.data
    return evt.data


@pytest.mark.skip(reason="Test has to be fixed.")
def test_run_simple_project(start_processes: None, ars: ARServer) -> None:

    event(ars, events.c.ShowMainScreen)

    assert ars.call_rpc(
        rpc.s.NewScene.Request(uid(), rpc.s.NewScene.Request.Args("Test scene")), rpc.s.NewScene.Response
    ).result

    scene_data = event(ars, events.s.OpenScene).data
    assert scene_data
    scene = scene_data.scene

    assert ars.call_rpc(
        rpc.s.AddObjectToScene.Request(
            uid(), rpc.s.AddObjectToScene.Request.Args("time_actions", TimeActions.__name__)
        ),
        rpc.s.AddObjectToScene.Response,
    ).result

    obj = event(ars, events.s.SceneObjectChanged).data
    assert obj

    assert ars.call_rpc(
        rpc.p.NewProject.Request(uid(), rpc.p.NewProject.Request.Args(scene.id, "Project name")),
        rpc.p.NewProject.Response,
    ).result

    proj = event(ars, events.p.OpenProject).data
    assert proj

    assert ars.call_rpc(
        rpc.p.AddActionPoint.Request(uid(), rpc.p.AddActionPoint.Request.Args("ap1", common.Position())),
        rpc.p.AddActionPoint.Response,
    ).result

    ap = event(ars, events.p.ActionPointChanged).data
    assert ap is not None

    assert ars.call_rpc(
        rpc.p.AddAction.Request(
            uid(),
            rpc.p.AddAction.Request.Args(
                ap.id,
                "test_action",
                f"{obj.id}/{TimeActions.sleep.__name__}",
                [common.ActionParameter("seconds", "double", "0.5")],
                [common.Flow()],
            ),
        ),
        rpc.p.AddAction.Response,
    ).result

    action = event(ars, events.p.ActionChanged).data
    assert action is not None

    add_logic_item(ars, common.LogicItem.START, action.id)
    add_logic_item(ars, action.id, common.LogicItem.END)

    save_project(ars)

    LOGGER.debug(persistent_storage.get_project(proj.project.id))

    # TODO test also temporary package

    close_project(ars)

    event(ars, events.c.ShowMainScreen)

    assert ars.call_rpc(
        rpc.b.BuildProject.Request(uid(), rpc.b.BuildProject.Request.Args(proj.project.id, "Package name")),
        rpc.b.BuildProject.Response,
    ).result

    package = event(ars, eevents.PackageChanged).data
    assert package is not None

    assert ars.call_rpc(
        erpc.RunPackage.Request(uid(), erpc.RunPackage.Request.Args(package.id)), erpc.RunPackage.Response
    ).result

    ps = event(ars, arcor2_events.PackageState).data
    assert ps
    assert ps.package_id == package.id
    assert ps.state == ps.state.RUNNING

    pi = event(ars, arcor2_events.PackageInfo).data
    assert pi
    assert pi.package_id == package.id

    act_in = event(ars, arcor2_events.CurrentAction).data
    assert act_in
    assert act_in.action_id == action.id
    # assert len(act_in.args) == 1
    # assert act_in.args[0].name == "seconds"
    # assert act_in.args[0].type == "double"
    # assert act_in.args[0].value == "0.1"

    act_state_before = event(ars, arcor2_events.ActionState).data
    assert act_state_before
    assert act_state_before.method == TimeActions.sleep.__name__
    assert act_state_before.where == act_state_before.where.BEFORE

    act_state_after = event(ars, arcor2_events.ActionState).data
    assert act_state_after
    assert act_state_after.method == TimeActions.sleep.__name__
    assert act_state_after.where == act_state_after.where.AFTER

    # TODO pause, resume

    assert ars.call_rpc(erpc.StopPackage.Request(uid()), erpc.StopPackage.Response).result

    ps2 = wait_for_event(ars, arcor2_events.PackageState).data
    assert ps2
    assert ps2.package_id == package.id
    assert ps2.state == ps.state.STOPPED

    show_main_screen_event = event(ars, events.c.ShowMainScreen)
    assert show_main_screen_event.data
    assert show_main_screen_event.data.what == events.c.ShowMainScreen.Data.WhatEnum.PackagesList
    assert show_main_screen_event.data.highlight == package.id
