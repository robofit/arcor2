import logging
import os
import random
import signal
import subprocess as sp
import time
from typing import Any, Iterator, NamedTuple

import pytest

from arcor2.helpers import find_free_port
from arcor2_arserver.tests.testutils import CheckHealthException, check_health, log_proc_output
from arcor2_storage import client as storage_client

LOGGER = logging.getLogger(__name__)


class Urls(NamedTuple):
    ros_domain_id: str
    robot_url: str
    storage_url: str


def _finish_processes(processes: list[sp.Popen]) -> None:
    for proc in processes:
        if proc.poll() is None:
            try:
                os.killpg(proc.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass

            try:
                proc.wait(timeout=5)
            except sp.TimeoutExpired:
                try:
                    os.killpg(proc.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                proc.wait(timeout=1)

        log_proc_output(proc.communicate())


def _load_ros_env() -> dict[str, str]:
    try:
        output = sp.check_output(
            ["bash", "-lc", "source /opt/ros/jazzy/setup.bash >/dev/null && env -0"],
            text=False,
            env={},
        )
    except sp.CalledProcessError as exc:
        raise RuntimeError("Failed to source /opt/ros/jazzy/setup.bash") from exc

    env: dict[str, str] = {}

    for chunk in output.split(b"\0"):
        if not chunk:
            continue

        key, _, value = chunk.partition(b"=")
        env[key.decode()] = value.decode()

    return env


def _ros_launch_env(env: dict[str, str]) -> dict[str, str]:
    launch_env = {key: value for key, value in env.items() if not key.startswith("PEX_")}

    for key in ("PYTEST_DISABLE_PLUGIN_AUTOLOAD", "PYTEST_PLUGINS", "PYTHONDEVMODE", "PYTHONWARNINGS"):
        launch_env.pop(key, None)

    return launch_env


def _assert_process_alive(proc: sp.Popen, error_message: str) -> None:
    if proc.poll() is not None:
        log_proc_output(proc.communicate())
        raise RuntimeError(error_message)


@pytest.fixture(scope="module", params=["ur5e"])
def start_processes(request) -> Iterator[Urls]:
    ros_domain_id = str(random.sample(range(0, 232 + 1), 1)[0])
    ur_type: str = request.param

    processes: list[sp.Popen] = []

    ros_env = _load_ros_env()

    my_env = os.environ.copy()
    my_env.update(ros_env)
    my_env["ROS_DOMAIN_ID"] = ros_domain_id

    ros_launch_env = _ros_launch_env(my_env)

    kwargs: dict[str, Any] = {
        "env": my_env,
        "stdout": sp.PIPE,
        "stderr": sp.STDOUT,
        "start_new_session": True,
    }

    ur_control_proc = sp.Popen(
        [
            "ros2",
            "launch",
            "ur_robot_driver",
            "ur_control.launch.py",
            "launch_rviz:=false",
            f"ur_type:={ur_type}",
            "use_mock_hardware:=true",
            "robot_ip:=xyz",
        ],
        env=ros_launch_env,
        stdout=sp.PIPE,
        stderr=sp.STDOUT,
        start_new_session=True,
    )

    processes.append(ur_control_proc)

    time.sleep(3)
    _assert_process_alive(ur_control_proc, "UR control launch died.")

    storage_port = find_free_port()
    storage_url = f"http://127.0.0.1:{storage_port}"

    my_env["ARCOR2_STORAGE_SERVICE_PORT"] = str(storage_port)
    my_env["ARCOR2_STORAGE_SERVICE_URL"] = storage_url
    my_env["ARCOR2_STORAGE_DB_PATH"] = f"/tmp/arcor2_storage_{ros_domain_id}.sqlite"

    storage_client.URL = storage_url

    storage_proc = sp.Popen(
        ["python", "src.python.arcor2_storage.scripts/storage.pex"],
        **kwargs,
    )

    processes.append(storage_proc)

    if storage_proc.poll() is not None:
        _finish_processes(processes)
        raise RuntimeError("Storage service died.")

    try:
        check_health("Storage", storage_url, timeout=20)
    except CheckHealthException:
        _finish_processes(processes)
        raise

    robot_url = f"http://0.0.0.0:{find_free_port()}"

    my_env["ARCOR2_UR_URL"] = robot_url
    my_env["ARCOR2_UR_INTERACT_WITH_DASHBOARD"] = "false"
    my_env["ARCOR2_UR_TYPE"] = ur_type
    my_env["PEX_EXTRA_SYS_PATH"] = "/opt/ros/jazzy/lib/python3.12/site-packages"
    my_env["ARCOR2_REST_API_DEBUG"] = "true"

    robot_proc = sp.Popen(
        ["python", "src.python.arcor2_ur.scripts/ur.pex"],
        **kwargs,
    )

    processes.append(robot_proc)

    if robot_proc.poll() is not None:
        _finish_processes(processes)
        raise RuntimeError("Robot service died.")

    try:
        check_health("UR", robot_url, timeout=20)
    except CheckHealthException:
        _finish_processes(processes)
        raise

    robot_pub_proc = sp.Popen(
        ["python", "src.python.arcor2_ur.scripts/robot_publisher.pex"],
        **kwargs,
    )

    processes.append(robot_pub_proc)

    if robot_pub_proc.poll() is not None:
        _finish_processes(processes)
        raise RuntimeError("Robot publisher node died.")

    yield Urls(ros_domain_id, robot_url, storage_url)

    _finish_processes(processes)
