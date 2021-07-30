import os
import subprocess
from typing import Iterator

import pytest

from arcor2.clients import scene_service
from arcor2.data.common import Pose
from arcor2.data.object_type import Box
from arcor2.helpers import find_free_port
from arcor2.object_types.abstract import CollisionObject


def finish_processes(processes) -> None:

    for proc in processes:
        proc.terminate()
        proc.wait()
        print(proc.communicate())


@pytest.fixture()
def start_processes() -> Iterator[None]:

    my_env = os.environ.copy()

    scene_port = find_free_port()
    scene_url = f"http://0.0.0.0:{scene_port}"

    my_env["ARCOR2_SCENE_SERVICE_URL"] = scene_url
    my_env["ARCOR2_SCENE_SERVICE_MOCK_PORT"] = str(scene_port)
    scene_service.URL = scene_url

    processes = []

    for cmd in ("./src.python.arcor2_mocks.scripts/mock_scene.pex",):
        processes.append(subprocess.Popen(cmd, env=my_env, stdout=subprocess.PIPE))

    scene_service.wait_for(20)

    yield None

    finish_processes(processes)


def test_generic_with_pose(start_processes: None) -> None:

    obj = CollisionObject("id", "name", Pose(), Box("boxId", 0.1, 0.1, 0.1))
    assert obj.id in scene_service.collision_ids()

    obj.pose = Pose()

    obj.enabled = False
    assert obj.id not in scene_service.collision_ids()
    obj.enabled = True
    assert obj.id in scene_service.collision_ids()

    scene_service.start()
    assert obj.id in scene_service.collision_ids()
    scene_service.stop()  # after stop, all collisions are removed by the Scene service
    assert not scene_service.collision_ids()
