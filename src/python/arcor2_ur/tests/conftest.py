import logging
import os
import random
import signal
import subprocess as sp
import time
from typing import Iterator, NamedTuple

import pytest

from arcor2.helpers import find_free_port
from arcor2_arserver.tests.testutils import CheckHealthException, check_health, log_proc_output

LOGGER = logging.getLogger(__name__)


class Urls(NamedTuple):
    ros_domain_id: str
    robot_url: str


def _finish_processes(processes) -> None:
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
    """Load environment variables from ROS setup script."""
    try:
        output = sp.check_output(
            ["bash", "-lc", "source /opt/ros/jazzy/setup.bash >/dev/null && env -0"],
            text=False,
            env={},
        )
    except sp.CalledProcessError as exc:  # pragma: no cover - best effort helper
        raise RuntimeError("Failed to source /opt/ros/jazzy/setup.bash") from exc

    env: dict[str, str] = {}
    for chunk in output.split(b"\0"):
        if not chunk:
            continue
        key, _, value = chunk.partition(b"=")
        env[key.decode()] = value.decode()
    return env


@pytest.fixture(scope="module", params=["ur5e"])
def start_processes(request) -> Iterator[Urls]:
    """Starts Dobot dependencies."""

    ros_domain_id = str(random.sample(range(0, 232 + 1), 1)[0])
    ur_type: str = request.param

    processes = []
    ros_env = _load_ros_env()
    my_env = os.environ.copy()
    my_env.update(ros_env)
    my_env["ROS_DOMAIN_ID"] = ros_domain_id

    # Keep ROS view of the world dominant; strip test-only/debug env for the ROS launcher
    ros_launch_env = {k: v for k, v in my_env.items() if not k.startswith("PEX_")}
    for key in ("PYTEST_DISABLE_PLUGIN_AUTOLOAD", "PYTEST_PLUGINS", "PYTHONDEVMODE", "PYTHONWARNINGS"):
        ros_launch_env.pop(key, None)

    kwargs = {"env": my_env, "stdout": sp.PIPE, "stderr": sp.STDOUT, "start_new_session": True}

    processes.append(
        sp.Popen(
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
    )
    time.sleep(3)  # TODO find another way how to make sure that everything is running
    if processes[-1].poll():
        log_proc_output(processes[-1].communicate())
        raise Exception("Launch died...")

    robot_url = f"http://0.0.0.0:{find_free_port()}"
    my_env["ARCOR2_UR_URL"] = robot_url
    my_env["ARCOR2_UR_INTERACT_WITH_DASHBOARD"] = "false"
    my_env["ARCOR2_UR_TYPE"] = ur_type
    my_env["PEX_EXTRA_SYS_PATH"] = "/opt/ros/jazzy/lib/python3.12/site-packages"
    my_env["ARCOR2_REST_API_DEBUG"] = "true"

    robot_proc = sp.Popen(["python", "src.python.arcor2_ur.scripts/ur.pex"], **kwargs)  # type: ignore

    processes.append(robot_proc)

    if robot_proc.poll():
        _finish_processes(processes)
        raise Exception("Robot service died.")

    try:
        check_health("UR", robot_url, timeout=20)
    except CheckHealthException:
        _finish_processes(processes)
        raise

    # robot_mode etc. is not published with mock_hw -> there is this helper node to do that
    # it can't be published from here as it depends on ROS (Python 3.12)
    robot_pub_proc = sp.Popen(["python", "src.python.arcor2_ur.scripts/robot_publisher.pex"], **kwargs)  # type: ignore
    processes.append(robot_pub_proc)

    if robot_pub_proc.poll():
        _finish_processes(processes)
        raise Exception("Robot publisher node died.")

    yield Urls(ros_domain_id, robot_url)

    _finish_processes(processes)
