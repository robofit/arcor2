import logging
import os
import random
import subprocess as sp
import sys
import time
from typing import Iterator, NamedTuple

import pytest

from arcor2.helpers import find_free_port
from arcor2_arserver.tests.testutils import CheckHealthException, check_health, finish_processes, log_proc_output

LOGGER = logging.getLogger(__name__)


class Urls(NamedTuple):
    ros_domain_id: str
    robot_url: str


@pytest.fixture(scope="module", params=["ur5e"])
def start_processes(request) -> Iterator[Urls]:
    """Starts Dobot dependencies."""

    ros_domain_id = str(random.sample(range(0, 232 + 1), 1)[0])
    ur_type: str = request.param

    processes = []
    my_env = os.environ.copy()
    my_env["ROS_DOMAIN_ID"] = ros_domain_id
    my_env["AMENT_PREFIX_PATH"] = "/opt/ros/jazzy"

    pypath = ":".join(sys.path)
    my_env["PYTHONPATH"] = pypath

    kwargs = {"env": my_env, "stdout": sp.PIPE, "stderr": sp.STDOUT}

    processes.append(
        sp.Popen(  # type: ignore
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
            **kwargs,
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

    robot_proc = sp.Popen(["python", "src.python.arcor2_ur.scripts/ur.pex"], **kwargs)  # type: ignore

    processes.append(robot_proc)

    if robot_proc.poll():
        finish_processes(processes)
        raise Exception("Robot service died.")

    try:
        check_health("UR", robot_url, timeout=20)
    except CheckHealthException:
        finish_processes(processes)
        raise

    # robot_mode etc. is not published with mock_hw -> there is this helper node to do that
    # it can't be published from here as it depends on ROS (Python 3.12)
    robot_pub_proc = sp.Popen(["python", "src.python.arcor2_ur.scripts/robot_publisher.pex"], **kwargs)  # type: ignore
    processes.append(robot_pub_proc)

    if robot_pub_proc.poll():
        finish_processes(processes)
        raise Exception("Robot publisher node died.")

    yield Urls(ros_domain_id, robot_url)

    finish_processes(processes)
