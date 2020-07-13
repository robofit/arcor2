# -*- coding: utf-8 -*-

import os
import subprocess
import tempfile
import time
import uuid
from typing import Iterator, Type, TypeVar

import pytest  # type: ignore

import websocket  # type: ignore

from arcor2.data import events, rpc
from arcor2.nodes.project_mock import PORT as PROJECT_MOCK_PORT


def finish_processes(processes) -> None:

    for proc in processes:
        proc.terminate()
        proc.wait()
        print(proc.communicate())


@pytest.fixture()
def ws_client() -> Iterator[websocket.WebSocket]:

    with tempfile.TemporaryDirectory() as tmp_dir:

        my_env = os.environ.copy()
        my_env["ARCOR2_DATA_PATH"] = tmp_dir
        my_env["ARCOR2_PERSISTENT_STORAGE_URL"] = f"http://0.0.0.0:{PROJECT_MOCK_PORT}"

        processes = []

        for cmd in ("arcor2_project_mock", "arcor2_execution", "arcor2_server"):
            processes.append(subprocess.Popen(cmd, env=my_env, stdout=subprocess.PIPE))

        ws = websocket.WebSocket()

        time.sleep(5)  # TODO how to avoid this? ws.connect/timeout probably does not work...

        try:
            ws.connect("ws://0.0.0.0:6789", timeout=5)
        except ConnectionRefusedError:

            finish_processes(processes)
            return

        yield ws

        ws.close()
        finish_processes(processes)


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


def test_scene_basic_rpcs(ws_client: websocket.WebSocket) -> None:

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
