# -*- coding: utf-8 -*-

import os
import subprocess
import tempfile
import time
import uuid
from contextlib import contextmanager
from typing import Iterator, Type, TypeVar

import pytest  # type: ignore

import websocket  # type: ignore

from arcor2.data import common, events, object_type, rpc
from arcor2.nodes.project_mock import PORT as PROJECT_MOCK_PORT


def finish_processes(processes) -> None:

    for proc in processes:
        proc.terminate()
        proc.wait()
        print(proc.communicate())


@pytest.fixture()
def start_processes() -> Iterator[None]:

    with tempfile.TemporaryDirectory() as tmp_dir:

        my_env = os.environ.copy()
        my_env["ARCOR2_DATA_PATH"] = tmp_dir
        my_env["ARCOR2_PERSISTENT_STORAGE_URL"] = f"http://0.0.0.0:{PROJECT_MOCK_PORT}"

        processes = []

        for cmd in ("arcor2_project_mock", "arcor2_execution", "arcor2_server"):
            processes.append(subprocess.Popen(cmd, env=my_env, stdout=subprocess.PIPE))

        yield None

        finish_processes(processes)


WS_CONNECTION_STR = "ws://0.0.0.0:6789"


@pytest.fixture()
def ws_client() -> Iterator[websocket.WebSocket]:

    ws = websocket.WebSocket()
    start_time = time.monotonic()
    while time.monotonic() < start_time + 10.0:
        try:
            ws.connect(WS_CONNECTION_STR)  # timeout param probably does not work
            break
        except ConnectionRefusedError:
            time.sleep(0.25)
    yield ws
    ws.close()


@contextmanager
def managed_ws_client():
    ws = websocket.WebSocket()
    ws.connect(WS_CONNECTION_STR)
    yield ws
    ws.close()


E = TypeVar("E", bound=events.Event)


def event(ws_client: websocket.WebSocket, evt_type: Type[E]) -> E:

    evt = evt_type.from_json(ws_client.recv())
    assert evt.event == evt_type.event
    return evt


RR = TypeVar("RR", bound=rpc.common.Response)


def uid() -> int:
    return uuid.uuid4().int


def call_rpc(ws_client: websocket.WebSocket, req: rpc.common.Request, resp_type: Type[RR]) -> RR:

    ws_client.send(req.to_json())
    resp = resp_type.from_json(ws_client.recv())
    assert req.id == resp.id
    assert req.request == resp.response
    return resp


@pytest.fixture()
def scene(ws_client: websocket.WebSocket) -> Iterator[common.Scene]:

    event(ws_client, events.ShowMainScreenEvent)

    test = "Test scene"

    call_rpc(
        ws_client,
        rpc.scene.NewSceneRequest(uid(), rpc.scene.NewSceneRequestArgs(test, test)),
        rpc.scene.NewSceneResponse
    )

    scene_evt = event(ws_client, events.OpenScene)
    assert scene_evt.data

    test_type = "TestType"

    assert call_rpc(
        ws_client,
        rpc.objects.NewObjectTypeRequest(uid(), object_type.ObjectTypeMeta(test_type, base="Generic")),
        rpc.objects.NewObjectTypeResponse
    ).result

    event(ws_client, events.ChangedObjectTypesEvent)

    assert call_rpc(
        ws_client,
        rpc.scene.AddObjectToSceneRequest(uid(),
                                          rpc.scene.AddObjectToSceneRequestArgs("test_type", test_type, common.Pose())),
        rpc.scene.AddObjectToSceneResponse
    )

    event(ws_client, events.SceneObjectChanged)

    call_rpc(ws_client, rpc.scene.SaveSceneRequest(uid()), rpc.scene.SaveSceneResponse)
    event(ws_client, events.SceneSaved)
    call_rpc(ws_client, rpc.scene.CloseSceneRequest(uid()), rpc.scene.CloseSceneResponse)
    event(ws_client, events.SceneClosed)
    event(ws_client, events.ShowMainScreenEvent)

    yield scene_evt.data.scene


def test_scene_basic_rpcs(start_processes: None, ws_client: websocket.WebSocket) -> None:

    test = "Test"

    # initial event
    show_main_screen_event = event(ws_client, events.ShowMainScreenEvent)
    assert show_main_screen_event.data
    assert show_main_screen_event.data.what == events.ShowMainScreenData.WhatEnum.ScenesList

    # first, there are no scenes
    scenes = call_rpc(ws_client, rpc.scene.ListScenesRequest(uid()), rpc.scene.ListScenesResponse)
    assert scenes.result
    assert not scenes.data

    assert call_rpc(ws_client,
                    rpc.scene.NewSceneRequest(uid(), rpc.scene.NewSceneRequestArgs(test, test)),
                    rpc.scene.NewSceneResponse).result

    open_scene_event = event(ws_client, events.OpenScene)
    assert open_scene_event.parent_id is None
    assert open_scene_event.change_type is None
    assert open_scene_event.data
    assert open_scene_event.data.scene.id
    scene_id = open_scene_event.data.scene.id
    assert open_scene_event.data.scene.name == test
    assert open_scene_event.data.scene.desc == test
    assert not open_scene_event.data.scene.objects
    assert not open_scene_event.data.scene.services

    # attempt to create a new scene while scene is open should fail
    assert not call_rpc(ws_client,
                        rpc.scene.NewSceneRequest(uid(), rpc.scene.NewSceneRequestArgs(test, test)),
                        rpc.scene.NewSceneResponse).result

    assert call_rpc(ws_client, rpc.scene.SaveSceneRequest(uid()), rpc.scene.SaveSceneResponse).result

    event(ws_client, events.SceneSaved)

    assert call_rpc(ws_client, rpc.scene.CloseSceneRequest(uid()), rpc.scene.CloseSceneResponse).result

    event(ws_client, events.SceneClosed)

    show_main_screen_event_2 = event(ws_client, events.ShowMainScreenEvent)
    assert show_main_screen_event_2.data
    assert show_main_screen_event_2.data.what == events.ShowMainScreenData.WhatEnum.ScenesList
    assert show_main_screen_event_2.data.highlight == scene_id

    # attempt to open non-existent scene
    assert not call_rpc(ws_client,
                        rpc.scene.OpenSceneRequest(uid(), rpc.common.IdArgs("some-random-nonsense")),
                        rpc.scene.OpenSceneResponse).result

    list_of_scenes = call_rpc(ws_client, rpc.scene.ListScenesRequest(uid()), rpc.scene.ListScenesResponse)
    assert list_of_scenes.result
    assert len(list_of_scenes.data) == 1
    assert list_of_scenes.data[0].id == scene_id

    # open previously saved scene
    assert call_rpc(ws_client,
                    rpc.scene.OpenSceneRequest(uid(), rpc.scene.IdArgs(scene_id)),
                    rpc.scene.OpenSceneResponse).result

    open_scene_event_2 = event(ws_client, events.OpenScene)
    assert open_scene_event_2.data
    assert open_scene_event_2.data.scene.id == scene_id

    assert call_rpc(ws_client, rpc.scene.CloseSceneRequest(uid()), rpc.scene.CloseSceneResponse).result
    event(ws_client, events.SceneClosed)

    show_main_screen_event_3 = event(ws_client, events.ShowMainScreenEvent)
    assert show_main_screen_event_3.data
    assert show_main_screen_event_3.data.what == events.ShowMainScreenData.WhatEnum.ScenesList
    assert show_main_screen_event_3.data.highlight == scene_id

    with managed_ws_client() as ws_client_2:

        smse = event(ws_client_2, events.ShowMainScreenEvent)
        assert smse.data
        assert smse.data.what == events.ShowMainScreenData.WhatEnum.ScenesList
        assert smse.data.highlight is None

    assert call_rpc(ws_client,
                    rpc.scene.DeleteSceneRequest(uid(), rpc.common.IdArgs(scene_id)),
                    rpc.scene.DeleteSceneResponse).result

    scene_changed_evt = event(ws_client, events.SceneChanged)
    assert scene_changed_evt.data
    assert scene_changed_evt.data.id == scene_id
    assert scene_changed_evt.change_type == events.EventType.REMOVE

    list_of_scenes_2 = call_rpc(ws_client, rpc.scene.ListScenesRequest(uid()), rpc.scene.ListScenesResponse)
    assert list_of_scenes_2.result
    assert not list_of_scenes_2.data


def test_project_basic_rpcs(start_processes: None, ws_client: websocket.WebSocket, scene: common.Scene) -> None:

    # first, there are no projects
    projects = call_rpc(ws_client, rpc.project.ListProjectsRequest(uid()), rpc.project.ListProjectsResponse)
    assert projects.result
    assert not projects.data

    project_name = "Test project"

    # attempt to use non-existent scene_id
    assert not call_rpc(
        ws_client,
        rpc.project.NewProjectRequest(uid(), rpc.project.NewProjectRequestArgs("some non-sense string", project_name)),
        rpc.project.NewProjectResponse
    ).result

    # attempt to open non-existent project
    assert not call_rpc(
        ws_client,
        rpc.project.OpenProjectRequest(uid(), rpc.common.IdArgs("some-random-nonsense")),
        rpc.project.OpenProjectResponse
    ).result

    # correct scene_id
    assert call_rpc(
        ws_client,
        rpc.project.NewProjectRequest(uid(), rpc.project.NewProjectRequestArgs(scene.id, project_name)),
        rpc.project.NewProjectResponse
    ).result

    open_project_evt = event(ws_client, events.OpenProject)

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
    assert not call_rpc(
        ws_client,
        rpc.project.NewProjectRequest(uid(), rpc.project.NewProjectRequestArgs("some non-sense string", "blah")),
        rpc.project.NewProjectResponse
    ).result

    assert call_rpc(ws_client, rpc.project.SaveProjectRequest(uid()), rpc.project.SaveProjectResponse).result

    event(ws_client, events.ProjectSaved)

    assert call_rpc(ws_client, rpc.project.CloseProjectRequest(uid()), rpc.project.CloseProjectResponse).result

    event(ws_client, events.ProjectClosed)

    show_main_screen_event = event(ws_client, events.ShowMainScreenEvent)
    assert show_main_screen_event.data
    assert show_main_screen_event.data.what == events.ShowMainScreenData.WhatEnum.ProjectsList
    assert show_main_screen_event.data.highlight == project_id

    list_of_projects = call_rpc(ws_client, rpc.project.ListProjectsRequest(uid()), rpc.project.ListProjectsResponse)
    assert list_of_projects.result
    assert len(list_of_projects.data) == 1
    assert list_of_projects.data[0].id == project_id

    with managed_ws_client() as ws_client_2:

        smse = event(ws_client_2, events.ShowMainScreenEvent)
        assert smse.data
        assert smse.data.what == events.ShowMainScreenData.WhatEnum.ProjectsList
        assert smse.data.highlight is None

    # it should not be possible to delete scene used by a project
    assert not call_rpc(
        ws_client,
        rpc.scene.DeleteSceneRequest(uid(), rpc.common.IdArgs(scene.id)),
        rpc.scene.DeleteSceneResponse
    ).result

    assert call_rpc(
        ws_client,
        rpc.project.DeleteProjectRequest(uid(), rpc.common.IdArgs(project_id)),
        rpc.project.DeleteProjectResponse
    ).result

    project_changed_evt = event(ws_client, events.ProjectChanged)
    assert project_changed_evt.data
    assert project_changed_evt.data.id == project_id
    assert project_changed_evt.change_type == events.EventType.REMOVE

    assert call_rpc(
        ws_client,
        rpc.scene.DeleteSceneRequest(uid(), rpc.common.IdArgs(scene.id)),
        rpc.scene.DeleteSceneResponse
    ).result

    scene_changed_evt = event(ws_client, events.SceneChanged)
    assert scene_changed_evt.data
    assert scene_changed_evt.data.id == scene.id
    assert scene_changed_evt.change_type == events.EventType.REMOVE

    list_of_projects_2 = call_rpc(ws_client, rpc.project.ListProjectsRequest(uid()), rpc.project.ListProjectsResponse)
    assert list_of_projects_2.result
    assert not list_of_projects_2.data


def test_project_ap_rpcs(start_processes: None, ws_client: websocket.WebSocket, scene: common.Scene) -> None:

    assert call_rpc(
        ws_client,
        rpc.project.NewProjectRequest(uid(), rpc.project.NewProjectRequestArgs(scene.id, "Project name")),
        rpc.project.NewProjectResponse
    ).result

    event(ws_client, events.OpenProject)

    # TODO add object-AP, global AP, etc.
