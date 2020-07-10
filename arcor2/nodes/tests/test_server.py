# -*- coding: utf-8 -*-

import json
import logging
import os
import subprocess
import time
from typing import Iterator

import pytest  # type: ignore

import websocket  # type: ignore

from arcor2.data import events

# TODO helper function for RPC
# TODO upload some user object types
# TODO save project/scene
# TODO run/pause/resume/stop project

LOGGER = logging.getLogger(__name__)


@pytest.fixture()
def ws_client() -> Iterator[websocket.WebSocket]:

    my_env = os.environ.copy()
    my_env["ARCOR2_PERSISTENT_STORAGE_URL"] = ""

    processes = []

    for cmd in ("arcor2_project_mock", "arcor2_manager", "arcor2_server"):
        processes.append(subprocess.Popen(cmd, env=my_env, stdout=subprocess.PIPE))
        time.sleep(0.1)  # TODO figure out why is this needed

    ws = websocket.WebSocket()

    for _ in range(20):
        try:
            ws.connect("ws://0.0.0.0:6789", timeout=1)
            break
        except ConnectionRefusedError:
            time.sleep(1.0)
    else:
        raise ConnectionRefusedError("Failed to connect to server.")

    yield ws

    ws.close()

    for proc in processes:
        proc.terminate()
        proc.wait()


def wait_for_expected_events(ws_client: websocket.WebSocket) -> None:

    expected_events = [events.SceneChanged.event, events.ProjectChanged.event, events.PackageStateEvent.event]

    while expected_events:
        msg = json.loads(ws_client.recv())
        assert msg["event"] in expected_events

        expected_events.remove(msg["event"])
