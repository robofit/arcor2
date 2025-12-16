from datetime import datetime
from io import BytesIO

import humps

from arcor2.data.common import (
    IdDesc,
    Project,
    ProjectParameter,
    ProjectSources,
    Scene,
    SceneObject,
    SceneObjectOverride,
)
from arcor2.data.object_type import Box, MetaModel3d, Model3dType, ObjectType


def _camel(dc):
    return humps.camelize(dc.to_dict())


def test_asset_lifecycle(service_client) -> None:
    payload = {
        "assetData": (BytesIO(b"hello"), "hello.txt"),
    }

    resp = service_client.post("/assets", data=payload, content_type="multipart/form-data")
    assert resp.status_code == 200
    asset_info = resp.get_json()
    asset_id = asset_info["id"]

    assert service_client.get(f"/assets/{asset_id}/exists").get_json() is True
    assets = service_client.get("/assets/info").get_json()
    assert any(item["id"] == asset_id and item["fileName"] == "hello.txt" for item in assets)

    data_resp = service_client.get(f"/assets/{asset_id}/data")
    assert data_resp.data == b"hello"

    assert service_client.delete(f"/assets/{asset_id}").status_code == 200
    assert service_client.get(f"/assets/{asset_id}/exists").get_json() is False


def test_project_scene_and_models(service_client) -> None:
    # object type and model
    box_model = Box("Box", 0.1, 0.2, 0.3)
    model_resp = service_client.put("/models/box", json=_camel(box_model))
    assert model_resp.status_code == 200

    obj_type = ObjectType("Box", "print('box')", description="box", model=MetaModel3d("Box", Model3dType.BOX))
    ot_resp = service_client.put("/object-types", json=_camel(obj_type))
    assert ot_resp.status_code == 200

    # scene that references the object type
    scene = Scene("scene-one", id="scene1")
    scene.objects.append(SceneObject("box1", obj_type.id))
    scene_resp = service_client.put("/scenes", json=_camel(scene))
    assert scene_resp.status_code == 200

    # project & sources
    project = Project("proj", scene.id, description="demo", id="proj1")
    proj_resp = service_client.put("/projects", json=_camel(project))
    assert proj_resp.status_code == 200

    project_sources = ProjectSources(project.id, "print('src')")
    assert service_client.put("/projects/sources", json=_camel(project_sources)).status_code == 200
    assert service_client.get(f"/projects/{project.id}/sources").get_json()["script"] == "print('src')"

    # parameters & object parameters
    param = ProjectParameter("p1", "int", "3")
    pp_resp = service_client.put(f"/projects/{project.id}/parameters", json=[_camel(param)])
    assert datetime.fromisoformat(pp_resp.get_json())  # timestamp returned

    obj_param = SceneObjectOverride("box1", [])
    assert service_client.put(f"/projects/{project.id}/object-parameters", json=[_camel(obj_param)]).status_code == 200

    # clone project
    clone_resp = service_client.put(
        "/projects/clone",
        query_string={"project_id": project.id, "new_project_name": "clone-proj", "new_project_id": "proj2"},
    )
    assert clone_resp.status_code == 200
    cloned = clone_resp.get_json()
    assert cloned["id"] == "proj2"
    assert cloned["name"] == "clone-proj"

    # verify listings
    projects = service_client.get("/projects").get_json()
    assert {IdDesc.from_dict(humps.decamelize(p)).id for p in projects} == {project.id, "proj2"}

    scenes = service_client.get("/scenes").get_json()
    assert {IdDesc.from_dict(humps.decamelize(s)).id for s in scenes} == {scene.id}

    models = service_client.get("/models").get_json()
    assert any(item["id"] == "Box" for item in models)


def test_object_type_delete(service_client) -> None:
    obj_type = ObjectType("ToDelete", "print('x')")
    assert service_client.put("/object-types", json=_camel(obj_type)).status_code == 200
    assert service_client.delete("/object-types/ToDelete").status_code == 200
    # deleting non-existent returns error
    err = service_client.delete("/object-types/ToDelete")
    assert err.status_code == 500
