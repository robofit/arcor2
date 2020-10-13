import inspect
import logging
import os
import socket
import subprocess as sp
import tempfile
from contextlib import closing
from typing import Dict, Iterator, Tuple, Type, TypeVar

import pytest  # type: ignore

from arcor2.clients import persistent_storage, scene_service
from arcor2.data import common
from arcor2.data.events import Event
from arcor2.object_types.abstract import Generic, GenericWithPose
from arcor2.object_types.upload import upload_def
from arcor2_arserver.tests.objects.object_with_settings import ObjectWithSettings
from arcor2_arserver_data import events, objects, rpc
from arcor2_arserver_data.client import ARServer, uid
from arcor2_execution_data import EVENTS as EXE_EVENTS

LOGGER = logging.getLogger(__name__)


def find_free_port() -> int:
    with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as s:
        s.bind(("localhost", 0))
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        return s.getsockname()[1]


_arserver_port: int = 0


def log_proc_output(out: Tuple[bytes, bytes]) -> None:

    for line in out[0].decode().splitlines():
        LOGGER.error(line)


def finish_processes(processes) -> None:

    for proc in processes:
        proc.terminate()
        proc.wait()
        log_proc_output(proc.communicate())


@pytest.fixture()
def start_processes() -> Iterator[None]:

    global _arserver_port

    _arserver_port = find_free_port()

    with tempfile.TemporaryDirectory() as tmp_dir:

        my_env = os.environ.copy()

        project_port = find_free_port()
        project_url = f"http://0.0.0.0:{project_port}"
        my_env["ARCOR2_PERSISTENT_STORAGE_URL"] = project_url
        my_env["ARCOR2_PROJECT_SERVICE_MOCK_PORT"] = str(project_port)
        persistent_storage.URL = project_url

        scene_port = find_free_port()
        scene_url = f"http://0.0.0.0:{scene_port}"
        my_env["ARCOR2_SCENE_SERVICE_URL"] = scene_url
        my_env["ARCOR2_SCENE_SERVICE_MOCK_PORT"] = str(scene_port)
        scene_service.URL = scene_url

        my_env["ARCOR2_EXECUTION_URL"] = f"ws://0.0.0.0:{find_free_port()}"
        my_env["ARCOR2_PROJECT_PATH"] = os.path.join(tmp_dir, "packages")

        my_env["ARCOR2_SERVER_PORT"] = str(_arserver_port)
        my_env["ARCOR2_DATA_PATH"] = os.path.join(tmp_dir, "data")

        my_env["ARCOR2_BUILD_URL"] = f"http://0.0.0.0:{find_free_port()}"

        processes = []

        for cmd in (
            "./src.python.arcor2_mocks.scripts/mock_project.pex",
            "./src.python.arcor2_mocks.scripts/mock_scene.pex",
            "./src.python.arcor2_execution.scripts/execution.pex",
            "./src.python.arcor2_build.scripts/build.pex",
        ):
            processes.append(sp.Popen(cmd, env=my_env, stdout=sp.PIPE, stderr=sp.STDOUT))

        # it may take some time for project service to come up so give it some time
        for _ in range(3):
            upload_proc = sp.Popen(
                "./src.python.arcor2.scripts/upload_builtin_objects.pex", env=my_env, stdout=sp.PIPE, stderr=sp.STDOUT
            )
            ret = upload_proc.communicate()
            if upload_proc.returncode == 0:
                log_proc_output(ret)
                break
        else:
            raise Exception("Failed to upload objects.")

        upload_def(ObjectWithSettings)

        LOGGER.info(f"Starting ARServer listening on port  {_arserver_port}.")

        arserver_proc = sp.Popen(
            "./src.python.arcor2_arserver.scripts/arserver.pex", env=my_env, stdout=sp.PIPE, stderr=sp.STDOUT
        )

        processes.append(arserver_proc)
        assert arserver_proc.stdout is not None

        while True:
            line = arserver_proc.stdout.readline().decode().strip()
            if not line or "Server initialized." in line:  # TODO this is not ideal
                break

        if arserver_proc.poll():
            finish_processes(processes)
            raise Exception("ARServer died.")

        yield None

        finish_processes(processes)


def ars_connection_str() -> str:
    return f"ws://0.0.0.0:{_arserver_port}"


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

    with ARServer(ars_connection_str(), timeout=20, event_mapping=event_mapping) as ws:
        yield ws


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


def add_logic_item(ars: ARServer, start: str, end: str) -> common.LogicItem:

    assert ars.call_rpc(
        rpc.p.AddLogicItem.Request(uid(), rpc.p.AddLogicItem.Request.Args(start, end)), rpc.p.AddLogicItem.Response
    ).result

    evt = event(ars, events.p.LogicItemChanged)
    assert evt.data
    return evt.data


def save_project(ars: ARServer) -> None:

    assert ars.call_rpc(rpc.p.SaveProject.Request(uid()), rpc.p.SaveProject.Response).result
    event(ars, events.p.ProjectSaved)


def close_project(ars: ARServer) -> None:

    assert ars.call_rpc(rpc.p.CloseProject.Request(uid()), rpc.p.CloseProject.Response).result
    event(ars, events.p.ProjectClosed)
