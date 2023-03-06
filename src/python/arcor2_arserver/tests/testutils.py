import inspect
import logging
import os
import subprocess as sp
import tempfile
import time
from typing import Iterator, TypeVar

import pytest

from arcor2 import rest
from arcor2.clients import asset, project_service, scene_service
from arcor2.data import common
from arcor2.data.events import Event
from arcor2.data.rpc import get_id
from arcor2.helpers import find_free_port
from arcor2_arserver_data import events, rpc
from arcor2_arserver_data.client import ARServer
from arcor2_execution_data import EVENTS as EXE_EVENTS

LOGGER = logging.getLogger(__name__)


_arserver_port: int = 0


def log_proc_output(out: tuple[bytes, bytes]) -> None:
    for line in out[0].decode().splitlines():
        LOGGER.error(line)


def finish_processes(processes) -> None:
    for proc in processes:
        proc.terminate()
        proc.wait()
        log_proc_output(proc.communicate())


@pytest.fixture()
def start_processes(request) -> Iterator[None]:
    """Starts ARServer dependencies."""

    global _arserver_port

    additional_deps: None | list[str] = None

    if m := request.node.get_closest_marker("additional_deps"):
        additional_deps = m.args[0]

    with tempfile.TemporaryDirectory() as tmp_dir:
        try:
            processes = []
            my_env = os.environ.copy()
            kwargs = {"env": my_env, "stdout": sp.PIPE, "stderr": sp.STDOUT}

            project_port = find_free_port()
            project_url = f"http://0.0.0.0:{project_port}"
            my_env["ARCOR2_PROJECT_SERVICE_URL"] = project_url
            my_env["ARCOR2_PROJECT_SERVICE_MOCK_PORT"] = str(project_port)
            project_service.URL = project_url
            processes.append(
                sp.Popen(["python", "src.python.arcor2_mocks.scripts/mock_project.pex"], **kwargs)  # type: ignore
            )
            check_health("Project", project_url)

            asset_port = find_free_port()
            asset_url = f"http://0.0.0.0:{asset_port}"
            my_env["ARCOR2_ASSET_SERVICE_URL"] = asset_url
            my_env["ARCOR2_ASSET_SERVICE_MOCK_PORT"] = str(asset_port)
            asset.URL = asset_url
            processes.append(
                sp.Popen(["python", "src.python.arcor2_mocks.scripts/mock_asset.pex"], **kwargs)  # type: ignore
            )
            check_health("Asset", asset_url)

            scene_port = find_free_port()
            scene_url = f"http://0.0.0.0:{scene_port}"
            my_env["ARCOR2_SCENE_SERVICE_URL"] = scene_url
            my_env["ARCOR2_SCENE_SERVICE_PORT"] = str(scene_port)
            scene_service.URL = scene_url
            processes.append(
                sp.Popen(["python", "src.python.arcor2_scene.scripts/scene.pex"], **kwargs)  # type: ignore
            )
            scene_service.wait_for(60)

            my_env["ARCOR2_EXECUTION_URL"] = f"ws://0.0.0.0:{find_free_port()}"
            my_env["ARCOR2_PROJECT_PATH"] = os.path.join(tmp_dir, "packages")
            processes.append(
                sp.Popen(
                    ["python", "src.python.arcor2_execution.scripts/execution.pex", "--debug"], **kwargs
                )  # type: ignore
            )

            build_url = f"http://0.0.0.0:{find_free_port()}"
            my_env["ARCOR2_BUILD_URL"] = build_url
            processes.append(
                sp.Popen(["python", "src.python.arcor2_build.scripts/build.pex", "--debug"], **kwargs)  # type: ignore
            )

            check_health("Build", build_url)
        except CheckHealthException:
            finish_processes(processes)
            raise

        if additional_deps:
            for dep in additional_deps:
                LOGGER.info(f"Starting {dep}")
                add_proc = sp.Popen(["python"] + dep, **kwargs)  # type: ignore
                ret = add_proc.communicate()
                if add_proc.returncode != 0:
                    log_proc_output(ret)
                    raise Exception(f"Additional dependency {dep} failed.")

        _arserver_port = find_free_port()
        my_env["ARCOR2_ARSERVER_PORT"] = str(_arserver_port)
        my_env["ARCOR2_ARSERVER_CACHE_TIMEOUT"] = str(0.0)  # effectively disables the cache

        LOGGER.info(f"Starting ARServer listening on port  {_arserver_port}.")

        arserver_proc = sp.Popen(
            ["python", "src.python.arcor2_arserver.scripts/arserver.pex", "--debug"], **kwargs
        )  # type: ignore

        processes.append(arserver_proc)
        ARServer(ars_connection_str(), 30, event_mapping)

        if arserver_proc.poll():
            finish_processes(processes)
            raise Exception("ARServer died.")

        yield None

        finish_processes(processes)


class CheckHealthException(Exception):
    pass


def check_health(service_name: str, service_url: str, timeout: int = 60) -> None:
    for _ in range(timeout):
        try:
            rest.call(rest.Method.GET, f"{service_url}/healthz/ready")  # to check whether the service is running
            break
        except rest.RestException:
            pass
        time.sleep(1)
    else:
        raise CheckHealthException(f"{service_name} service at {service_url} is not responding.")


def ars_connection_str() -> str:
    return f"ws://0.0.0.0:{_arserver_port}"


# TODO refactor this into _data packages
event_mapping: dict[str, type[Event]] = {evt.__name__: evt for evt in EXE_EVENTS}

modules = []

for _, mod in inspect.getmembers(events, inspect.ismodule):
    modules.append(mod)

for mod in modules:
    for _, cls in inspect.getmembers(mod, inspect.isclass):
        if issubclass(cls, Event):
            event_mapping[cls.__name__] = cls


@pytest.fixture()
def ars() -> Iterator[ARServer]:
    with ARServer(ars_connection_str(), timeout=30, event_mapping=event_mapping) as ws:
        test_username = "testUser"
        assert ws.call_rpc(
            rpc.u.RegisterUser.Request(get_id(), rpc.u.RegisterUser.Request.Args(test_username)),
            rpc.u.RegisterUser.Response,
        ).result
        yield ws


E = TypeVar("E", bound=Event)


def event(ars: ARServer, evt_type: type[E]) -> E:
    evt = ars.get_event()
    assert isinstance(evt, evt_type)
    assert evt.event == evt_type.__name__
    return evt


def wait_for_event(ars: ARServer, evt_type: type[E]) -> E:
    evt = ars.get_event(drop_everything_until=evt_type)
    assert isinstance(evt, evt_type)
    assert evt.event == evt_type.__name__
    return evt


def add_logic_item(
    ars: ARServer, start: str, end: str, condition: None | common.ProjectLogicIf = None
) -> common.LogicItem:
    assert ars.call_rpc(
        rpc.p.AddLogicItem.Request(get_id(), rpc.p.AddLogicItem.Request.Args(start, end, condition)),
        rpc.p.AddLogicItem.Response,
    ).result

    evt = event(ars, events.p.LogicItemChanged)
    assert evt.data
    return evt.data


def save_project(ars: ARServer) -> None:
    assert ars.call_rpc(rpc.p.SaveProject.Request(get_id()), rpc.p.SaveProject.Response).result
    event(ars, events.p.ProjectSaved)


def close_project(ars: ARServer) -> None:
    assert ars.call_rpc(rpc.p.CloseProject.Request(get_id()), rpc.p.CloseProject.Response).result
    event(ars, events.p.ProjectClosed)


def lock_object(ars: ARServer, obj_id: str, lock_tree: bool = False) -> None:
    assert ars.call_rpc(
        rpc.lock.WriteLock.Request(get_id(), rpc.lock.WriteLock.Request.Args(obj_id, lock_tree)),
        rpc.lock.WriteLock.Response,
    ).result

    event(ars, events.lk.ObjectsLocked)


def unlock_object(ars: ARServer, obj_id: str) -> None:
    assert ars.call_rpc(
        rpc.lock.WriteUnlock.Request(get_id(), rpc.lock.WriteUnlock.Request.Args(obj_id)), rpc.lock.WriteUnlock.Response
    )

    event(ars, events.lk.ObjectsUnlocked)
