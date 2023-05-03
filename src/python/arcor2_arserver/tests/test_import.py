from datetime import datetime, timezone
from inspect import getsource
from io import BytesIO
from os import path
from zipfile import ZIP_DEFLATED, ZipFile

from humps import depascalize

from arcor2 import rest
from arcor2.cached import CachedProject
from arcor2.data.common import Action, ActionPoint, Flow, LogicItem, Position, Project, Scene, SceneObject
from arcor2.data.execution import PackageMeta
from arcor2.data.rpc.common import IdArgs
from arcor2.object_types.random_actions import RandomActions
from arcor2_arserver.tests.testutils import build_url_str
from arcor2_arserver_data import events, rpc
from arcor2_arserver_data.client import ARServer, get_id
from arcor2_build.source.utils import global_action_points_class

import_random_actions = """
import random
from typing import Optional

from arcor2.data.common import ActionMetadata
from arcor2.exceptions import Arcor2Exception
from arcor2.object_types.abstract import Generic\n"""

script = """
#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from action_points import ActionPoints
from object_types.random_actions import RandomActions
from arcor2_runtime.exceptions import print_exception

def main(res: Resources) -> None:
    aps = ActionPoints(res)
    random_actions: RandomActions = res.objects['obj_1']
    while True:
        bool_res1 = random_actions.random_bool(an='ac1')
        bool_res2 = random_actions.random_bool(an='ac2')

if __name__ == '__main__':
    try:
        with Resources() as res:
            main(res)
    except Exception as e:
        print_exception(e)"""


def create_test_package(project: Project, scene: Scene, script: str, package_name: str) -> BytesIO:
    mem_zip = BytesIO()

    with ZipFile(mem_zip, mode="w", compression=ZIP_DEFLATED) as zf:
        cached_project = CachedProject(project)

        data_path: str = "data"
        ot_path: str = "object_types"

        random_actions_src: str = import_random_actions + getsource(RandomActions)

        zf.writestr(path.join(ot_path, "__init__.py"), "")
        zf.writestr(path.join(data_path, "project.json"), project.to_json())
        zf.writestr(path.join(data_path, "scene.json"), scene.to_json())

        zf.writestr(path.join(ot_path, depascalize(scene.objects[0].type)) + ".py", random_actions_src)

        zf.writestr("script.py", script)

        zf.writestr("action_points.py", global_action_points_class(cached_project))

        zf.writestr("package.json", PackageMeta(package_name, datetime.now(tz=timezone.utc)).to_json())

    mem_zip.seek(0)

    return mem_zip


def test_import(start_processes: None, ars: ARServer) -> None:
    scene: Scene = Scene("s1", id="scene1")
    obj: SceneObject = SceneObject("random_actions", "RandomActions", id="obj_1")
    scene.objects.append(obj)

    project: Project = Project("p1", scene_id=scene.id, id="project1")
    ap1: ActionPoint = ActionPoint("ap1", Position())
    project.action_points.append(ap1)

    ac1: Action = Action("ac1", f"{obj.id}/random_bool", flows=[Flow(outputs=["bool_res"])])
    ap1.actions.append(ac1)

    project.logic.append(LogicItem(LogicItem.START, ac1.id))
    project.logic.append(LogicItem(ac1.id, LogicItem.END))

    params = {
        "overwriteScene": True,
        "overwriteProject": True,
        "overwriteObjectTypes": True,
        "overwriteProjectSources": True,
        "overwriteCollisionModels": True,
        "updateProjectFromScript": True,
    }
    url_build: str = build_url_str() + "/project/import"

    mem_zip = create_test_package(project, scene, script, "pkg_test")
    rest.call(rest.Method.PUT, url=url_build, params=params, files={"executionPackage": mem_zip.read()})

    assert ars.call_rpc(rpc.p.OpenProject.Request(get_id(), IdArgs("project1")), rpc.p.OpenProject.Response).result

    while True:
        evt = ars.get_event()
        if isinstance(evt, events.p.OpenProject):
            open_project_evt = evt
            break
        elif not evt:
            AssertionError()

    updated_project = open_project_evt.data.project

    c_updated_project = CachedProject(updated_project)

    if c_updated_project.actions[0].name == "ac1":
        assert c_updated_project.actions[0].type == "obj_1/random_bool"
        assert c_updated_project.actions[0].parameters == []
        assert c_updated_project.actions[0].flows[0].outputs == ["bool_res1"]

        assert c_updated_project.actions[1].name == "ac2"
        assert c_updated_project.actions[1].type == "obj_1/random_bool"
        assert c_updated_project.actions[1].parameters == []
        assert c_updated_project.actions[1].flows[0].outputs == ["bool_res2"]

        assert c_updated_project.find_logic_start_end(LogicItem.START, c_updated_project.actions[0].id)
        assert c_updated_project.find_logic_start_end(c_updated_project.actions[0].id, c_updated_project.actions[1].id)
        assert c_updated_project.find_logic_start_end(c_updated_project.actions[1].id, LogicItem.END)

    else:
        assert c_updated_project.actions[1].name == "ac1"
        assert c_updated_project.actions[1].type == "obj_1/random_bool"
        assert c_updated_project.actions[1].parameters == []
        assert c_updated_project.actions[1].flows[0].outputs == ["bool_res1"]

        assert c_updated_project.actions[0].name == "ac2"
        assert c_updated_project.actions[0].type == "obj_1/random_bool"
        assert c_updated_project.actions[0].parameters == []
        assert c_updated_project.actions[0].flows[0].outputs == ["bool_res2"]

        assert c_updated_project.find_logic_start_end(LogicItem.START, c_updated_project.actions[1].id)
        assert c_updated_project.find_logic_start_end(c_updated_project.actions[1].id, c_updated_project.actions[0].id)
        assert c_updated_project.find_logic_start_end(c_updated_project.actions[0].id, LogicItem.END)
