import requests
import os
import json
from typing import List

from arcor2.data import Project, Scene, ProjectSources, ObjectType, DataClassEncoder, IdDescList

URL = os.getenv("ARCOR2_PERSISTENT_STORAGE_URL", "http://127.0.0.1:5001")

# TODO async version
# TODO cache?
# TODO poll changes?


class PersistentStorageClient:

    def get_project(self, project_id: str) -> Project:

        resp = requests.get(f"{URL}/project/{project_id}")
        return Project.from_dict(json.loads(resp.text))

    def get_project_sources(self, project_id: str) -> ProjectSources:

        resp = requests.get(f"{URL}/project/{project_id}/sources")
        return ProjectSources.from_dict(json.loads(resp.text))

    def get_scene(self, scene_id: str) -> Scene:

        resp = requests.get(f"{URL}/scene/{scene_id}")
        return Scene.from_dict(json.loads(resp.text))

    def get_object_type(self, object_type_id: str) -> ObjectType:

        resp = requests.get(f"{URL}/object_type/{object_type_id}")
        return ObjectType.from_dict(json.loads(resp.text))

    def get_object_type_ids(self) -> IdDescList:
        resp = requests.get(f"{URL}/object_types")
        return IdDescList.from_dict(json.loads(resp.text))

    def update_project(self, project: Project):

        assert project.id
        requests.post(f"{URL}/project", json=json.dumps(project, cls=DataClassEncoder))

    def update_scene(self, scene: Scene):

        assert scene.id
        requests.post(f"{URL}/scene", json=json.dumps(scene, cls=DataClassEncoder))

    def update_project_sources(self, project_sources: ProjectSources):

        assert project_sources.id
        requests.post(f"{URL}/project/sources",
                      json=json.dumps(project_sources, cls=DataClassEncoder))

    def update_object_type(self, object_type: ObjectType):

        assert object_type.id
        requests.post(f"{URL}/object_type", json=json.dumps(object_type, cls=DataClassEncoder))
