import os
import subprocess as sp
import tempfile
import time
import zipfile
from typing import Iterator

import pytest

from arcor2 import rest
from arcor2.clients import project_service as ps
from arcor2.data.common import Project, ProjectSources, Scene, SceneObject
from arcor2.data.object_type import ObjectType
from arcor2.helpers import find_free_port

build_url = ""


def finish_processes(processes) -> None:
    for proc in processes:
        proc.terminate()
        proc.wait()
        print(proc.communicate()[0].decode("utf-8").strip())


def check_health(service_name: str, service_url: str, timeout: int = 60) -> None:
    for _ in range(timeout):
        try:
            rest.call(rest.Method.GET, f"{service_url}/healthz/ready")  # to check whether the service is running
            break
        except rest.RestException:
            pass
        time.sleep(1)
    else:
        pytest.exit(f"{service_name} service at {service_url} is not responding.", returncode=2)


@pytest.fixture
def start_processes() -> Iterator[None]:
    global build_url

    my_env = os.environ.copy()
    kwargs = {"env": my_env, "stdout": sp.PIPE, "stderr": sp.STDOUT}

    project_port = find_free_port()
    project_url = f"http://0.0.0.0:{project_port}"
    my_env["ARCOR2_PROJECT_SERVICE_URL"] = project_url
    my_env["ARCOR2_PROJECT_SERVICE_MOCK_PORT"] = str(project_port)
    ps.URL = project_url

    processes = []

    processes.append(sp.Popen(["python", "src.python.arcor2_mocks.scripts/mock_project.pex"], **kwargs))  # type: ignore

    check_health("Project", project_url)

    build_url = f"http://0.0.0.0:{find_free_port()}"
    my_env["ARCOR2_BUILD_URL"] = build_url
    my_env["ARCOR2_PROJECT_PATH"] = "whatever"
    processes.append(
        sp.Popen(["python", "src.python.arcor2_build.scripts/build.pex", "--debug"], **kwargs)  # type: ignore
    )
    check_health("Build", build_url)

    yield None

    finish_processes(processes)


additional_module = """
def whatever():
    return "whatever"
"""

ot1 = """
from arcor2.object_types.abstract import Generic
from .additional_module import whatever

class ObjectTypeOne(Generic):
    _ABSTRACT = False
"""

ot2 = """
from arcor2.object_types.abstract import Generic
from .object_type_one import ObjectTypeOne
from .additional_module import whatever

class ObjectTypeTwo(Generic):
    _ABSTRACT = False
"""


def test_cross_import(start_processes: None) -> None:
    ps.update_object_type(ObjectType("AdditionalModule", additional_module))
    ps.update_object_type(ObjectType("ObjectTypeOne", ot1))
    ps.update_object_type(ObjectType("ObjectTypeTwo", ot2))

    scene = Scene("test_scene")
    scene.objects.append(SceneObject("ot1", "ObjectTypeOne"))
    scene.objects.append(SceneObject("ot2", "ObjectTypeTwo"))

    ps.update_scene(scene)

    project = Project("test_project", scene.id)
    project.project_objects_ids = ["AdditionalModule"]
    project.has_logic = False
    ps.update_project(project)
    ps.update_project_sources(ProjectSources(project.id, "blah"))

    with tempfile.TemporaryDirectory() as tmpdirname:
        path = os.path.join(tmpdirname, "publish.zip")

        rest.download(
            f"{build_url}/project/publish",
            path,
            {
                "packageName": "test_package",
                "projectId": project.id,
            },
        )

        with zipfile.ZipFile(path) as zip_file:
            ot_dir_list = [name for name in zip_file.namelist() if name.startswith("object_types")]
            # there should be three OTs and __init__.py
            assert len(ot_dir_list) == 4, f"Strange content of object_types dir: {ot_dir_list}"

        assert {ot.id for ot in ps.get_object_type_ids()} == {"AdditionalModule", "ObjectTypeOne", "ObjectTypeTwo"}

        ps.delete_object_type("AdditionalModule")
        ps.delete_object_type("ObjectTypeOne")
        ps.delete_object_type("ObjectTypeTwo")

        with open(path, "rb") as fh:
            rest.call(rest.Method.PUT, url=f"{build_url}/project/import", files={"executionPackage": fh.read()})

        assert {ot.id for ot in ps.get_object_type_ids()} == {"AdditionalModule", "ObjectTypeOne", "ObjectTypeTwo"}
