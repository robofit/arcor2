# -*- coding: utf-8 -*-

import subprocess
import os
import json
import time
import uuid

import pytest  # type: ignore
import websocket  # type: ignore

from arcor2.data import rpc, events, object_type
from arcor2.object_types import Generic, Robot, Workspace

# TODO helper function for RPC
# TODO upload some user object types
# TODO save project/scene
# TODO run/pause/resume/stop project

pytest_plugins = ["docker_compose"]


@pytest.fixture()
def ws_client(request, function_scoped_container_getter):

    service = function_scoped_container_getter.get("arcor2_storage").network_info[0]
    api_url = "http://%s:%s/" % (service.hostname, service.host_port)

    my_env = os.environ.copy()
    my_env["ARCOR2_PERSISTENT_STORAGE_URL"] = api_url.strip("/")

    processes = []

    for cmd in ("arcor2_manager", "arcor2_server"):
        processes.append(subprocess.Popen(cmd, env=my_env, stdout=subprocess.PIPE))
        time.sleep(0.1)  # TODO figure out why is this needed

    ws = websocket.WebSocket()

    for _ in range(200):  # TODO how to have shorter time (20s?) on localhost while longer on CI?
        try:
            ws.connect("ws://localhost:6789", timeout=1)
            break
        except ConnectionRefusedError:
            time.sleep(1.0)
    else:
        raise ConnectionRefusedError("Failed to connect to server.")

    def fin():

        ws.close()

        for proc in processes:
            proc.terminate()
            proc.wait()

    request.addfinalizer(fin)

    return ws


def wait_for_expected_events(ws_client):

    expected_events = [events.SceneChangedEvent.event, events.ProjectChangedEvent.event, events.ProjectStateEvent.event]

    while expected_events:
        msg = json.loads(ws_client.recv())
        assert msg["event"] in expected_events

        expected_events.remove(msg["event"])


@pytest.mark.integration
def test_object_types(ws_client):

    wait_for_expected_events(ws_client)

    ws_client.send(rpc.GetObjectTypesRequest(id=uuid.uuid4().int).to_json())
    object_types = rpc.GetObjectTypesResponse.from_json(ws_client.recv())

    built_in_types = {Generic.__name__, Robot.__name__, Workspace.__name__}
    abstract_types = {Generic.__name__, Robot.__name__}

    for ot in object_types.data:
        assert ot.type in built_in_types, "Uncovered built-in object type!"
        assert not ot.needs_services
        assert ot.built_in

        if ot.type in abstract_types:
            assert ot.abstract

        ws_client.send(rpc.GetActionsRequest(id=uuid.uuid4().int, args=rpc.TypeArgs(ot.type)).to_json())
        rpc.GetActionsResponse.from_json(ws_client.recv())
        # TODO do some tests regarding actions?


@pytest.mark.integration
def test_new_object_type(ws_client):

    wait_for_expected_events(ws_client)

    test_type_name = "TestType"
    test_type_desc = "TestDescription"

    ws_client.send(rpc.NewObjectTypeRequest(id=uuid.uuid4().int,
                                            args=object_type.ObjectTypeMeta(test_type_name, test_type_desc)).to_json())
    resp = rpc.NewObjectTypeResponse.from_json(ws_client.recv())
    assert not resp.result, "Should return false as 'base' was not provided."

    ws_client.send(rpc.NewObjectTypeRequest(id=uuid.uuid4().int,
                                            args=object_type.ObjectTypeMeta(test_type_name,
                                                                            test_type_desc,
                                                                            base=Generic.__name__)).to_json())
    resp = rpc.NewObjectTypeResponse.from_json(ws_client.recv())
    assert resp.result

    ws_client.send(rpc.GetObjectTypesRequest(id=uuid.uuid4().int).to_json())

    # TODO order of event/response should be swapped, why is it like this?
    otc = events.ObjectTypesChangedEvent.from_json(ws_client.recv())
    assert otc.data[0] == test_type_name

    resp = rpc.GetObjectTypesResponse.from_json(ws_client.recv())
    for ot in resp.data:
        if ot.type == test_type_name:
            assert not ot.built_in
            # assert ot.description == test_type_desc # TODO description is not actually added there yet
            assert ot.base == Generic.__name__
            break
    else:
        pytest.fail("Object type name missing in the response.")
