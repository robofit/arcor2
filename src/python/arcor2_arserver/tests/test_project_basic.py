from arcor2.data import common
from arcor2.data.events import Event
from arcor2.data.rpc.common import IdArgs
from arcor2_arserver.tests.conftest import close_project, event, save_project
from arcor2_arserver_data import events, rpc
from arcor2_arserver_data.client import ARServer, get_id


def test_project_basic_rpcs(start_processes: None, ars: ARServer, scene: common.Scene) -> None:

    # first, there are no projects
    projects = ars.call_rpc(rpc.p.ListProjects.Request(get_id()), rpc.p.ListProjects.Response)
    assert projects.result
    assert not projects.data

    project_name = "Test project"

    # attempt to use non-existent scene_id
    assert not ars.call_rpc(
        rpc.p.NewProject.Request(get_id(), rpc.p.NewProject.Request.Args("some non-sense string", project_name)),
        rpc.p.NewProject.Response,
    ).result

    # attempt to open non-existent project
    assert not ars.call_rpc(
        rpc.p.OpenProject.Request(get_id(), IdArgs("some-random-nonsense")), rpc.p.OpenProject.Response
    ).result

    # correct scene_id
    assert ars.call_rpc(
        rpc.p.NewProject.Request(get_id(), rpc.p.NewProject.Request.Args(scene.id, project_name)),
        rpc.p.NewProject.Response,
    ).result

    open_project_evt = event(ars, events.p.OpenProject)
    event(ars, events.s.SceneState)

    assert open_project_evt.data
    assert open_project_evt.change_type is None
    assert open_project_evt.parent_id is None
    assert open_project_evt.data.scene.id == scene.id
    project_id = open_project_evt.data.project.id

    assert open_project_evt.data.project.name == project_name
    assert not open_project_evt.data.project.action_points
    assert len(open_project_evt.data.project.parameters) == 2  # scene_id + project_id
    assert not open_project_evt.data.project.functions
    assert not open_project_evt.data.project.logic

    # attempt to create project while another project is opened
    assert not ars.call_rpc(
        rpc.p.NewProject.Request(get_id(), rpc.p.NewProject.Request.Args("some non-sense string", "blah")),
        rpc.p.NewProject.Response,
    ).result

    save_project(ars)
    close_project(ars)

    show_main_screen_event = event(ars, events.c.ShowMainScreen)
    assert show_main_screen_event.data
    assert show_main_screen_event.data.what == events.c.ShowMainScreen.Data.WhatEnum.ProjectsList
    assert show_main_screen_event.data.highlight == project_id

    list_of_projects = ars.call_rpc(rpc.p.ListProjects.Request(get_id()), rpc.p.ListProjects.Response)
    assert list_of_projects.result
    assert list_of_projects.data
    assert len(list_of_projects.data) == 1
    assert list_of_projects.data[0].id == project_id

    get_scene_resp = ars.call_rpc(rpc.s.GetScene.Request(get_id(), IdArgs(scene.id)), rpc.s.GetScene.Response)
    assert get_scene_resp.result
    assert get_scene_resp.data
    assert get_scene_resp.data.id == scene.id  # actually whole scene should be the same (except 'modified')

    get_project_resp = ars.call_rpc(rpc.p.GetProject.Request(get_id(), IdArgs(project_id)), rpc.p.GetProject.Response)
    assert get_project_resp.result
    assert get_project_resp.data
    assert get_project_resp.data.id == project_id  # actually whole project should be the same (except 'modified')

    """ TODO: fix this
    with ARServer(WS_CONNECTION_STR, timeout=10, event_mapping=event_mapping) as ars_2:

        smse = event(ars_2, events.c.ShowMainScreen)
        assert smse.data
        assert smse.data.what == events.c.ShowMainScreen.Data.WhatEnum.ProjectsList
        assert smse.data.highlight is None
    """

    # it should not be possible to delete scene used by a project
    assert not ars.call_rpc(rpc.s.DeleteScene.Request(get_id(), IdArgs(scene.id)), rpc.s.DeleteScene.Response).result

    assert ars.call_rpc(rpc.p.DeleteProject.Request(get_id(), IdArgs(project_id)), rpc.p.DeleteProject.Response).result

    project_changed_evt = event(ars, events.p.ProjectChanged)
    assert project_changed_evt.data
    assert project_changed_evt.data.id == project_id
    assert project_changed_evt.change_type == Event.Type.REMOVE

    assert ars.call_rpc(rpc.s.DeleteScene.Request(get_id(), IdArgs(scene.id)), rpc.s.DeleteScene.Response).result

    scene_changed_evt = event(ars, events.s.SceneChanged)
    assert scene_changed_evt.data
    assert scene_changed_evt.data.id == scene.id
    assert scene_changed_evt.change_type == Event.Type.REMOVE

    list_of_projects_2 = ars.call_rpc(rpc.p.ListProjects.Request(get_id()), rpc.p.ListProjects.Response)
    assert list_of_projects_2.result
    assert not list_of_projects_2.data
