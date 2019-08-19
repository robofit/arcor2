# -*- coding: utf-8 -*-

import subprocess
import os
import json
import time

import pytest  # type: ignore
import websocket  # type: ignore

# TODO upload some user object types
# TODO save project/scene
# TODO run/pause/resume/stop project


@pytest.fixture()
def ws_client(request):

    my_env = os.environ.copy()
    my_env["ARCOR2_TESTING"] = "1"

    processes = []

    for cmd in ("arcor2_persistent_storage", "arcor2_manager", "arcor2_server"):
        processes.append(subprocess.Popen(cmd, env=my_env, stdout=subprocess.PIPE))

    ws = websocket.WebSocket()

    for _ in range(3):
        time.sleep(1.0)
        try:
            ws.connect("ws://localhost:6789", timeout=1)
            break
        except ConnectionRefusedError:
            pass
    else:
        raise ConnectionRefusedError("Failed to connect to server.")

    def fin():

        ws.close()

        for proc in processes:
            proc.kill()

    request.addfinalizer(fin)

    return ws


def wait_for_expected_events(ws_client):

    expected_events = ["sceneChanged", "projectChanged"]

    while expected_events:
        msg = json.loads(ws_client.recv())
        assert msg["event"] in expected_events

        expected_events.remove(msg["event"])


@pytest.mark.integration
def test_objects_actions(ws_client):

    wait_for_expected_events(ws_client)

    ws_client.send(json.dumps({"request": "getObjectTypes"}))

    object_types = json.loads(ws_client.recv())

    # TODO use RPC dataclass instead
    assert object_types["result"]
    assert not object_types["messages"]
    assert len(object_types["data"]) == 3

    ws_client.send(json.dumps({"request": "getObjectActions", "args": {"type": "Workspace"}}))

    workspace_actions = json.loads(ws_client.recv())

    assert workspace_actions["result"]
    assert not workspace_actions["messages"]


@pytest.mark.integration
def test_invalid_request(ws_client):
    """
    Invalid requests are completely ignored.
    """

    wait_for_expected_events(ws_client)

    ws_client.send(json.dumps({"request": "nonSenseRequest"}))

    with pytest.raises(websocket.WebSocketTimeoutException):
        ws_client.recv()

    # valid, but missing mandatory arg
    ws_client.send(json.dumps({"request": "getObjectActions", "args": {}}))

    with pytest.raises(websocket.WebSocketTimeoutException):
        ws_client.recv()
