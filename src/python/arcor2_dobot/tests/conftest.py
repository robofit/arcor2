import logging
import os
import subprocess as sp
from typing import Iterator, NamedTuple

import pytest

from arcor2.clients import scene_service
from arcor2.helpers import find_free_port
from arcor2_arserver.tests.testutils import check_health, finish_processes

LOGGER = logging.getLogger(__name__)


class Urls(NamedTuple):

    scene_url: str
    dobot_url: str


# TODO add m1 once there is ik/fk for it
@pytest.fixture(scope="module", params=["magician"])  # , "m1"])
def start_processes(request) -> Iterator[Urls]:
    """Starts Dobot dependencies."""

    processes = []
    my_env = os.environ.copy()
    kwargs = {"env": my_env, "stdout": sp.PIPE, "stderr": sp.STDOUT}

    scene_port = find_free_port()
    scene_url = f"http://0.0.0.0:{scene_port}"
    my_env["ARCOR2_SCENE_SERVICE_URL"] = scene_url
    my_env["ARCOR2_SCENE_SERVICE_PORT"] = str(scene_port)
    scene_service.URL = scene_url
    processes.append(sp.Popen("./src.python.arcor2_scene.scripts/scene.pex", **kwargs))  # type: ignore
    scene_service.wait_for(60)

    dobot_url = f"http://0.0.0.0:{find_free_port()}"
    my_env["ARCOR2_DOBOT_URL"] = dobot_url
    my_env["ARCOR2_DOBOT_MOCK"] = "1"
    my_env["ARCOR2_DOBOT_DEBUG"] = "1"
    my_env["ARCOR2_DOBOT_MODEL"] = request.param

    dobot_proc = sp.Popen(["./src.python.arcor2_dobot.scripts/dobot.pex"], **kwargs)  # type: ignore

    processes.append(dobot_proc)

    if dobot_proc.poll():
        finish_processes(processes)
        raise Exception("Dobot service died.")

    check_health("Dobot", dobot_url)

    yield Urls(scene_url, dobot_url)

    finish_processes(processes)
