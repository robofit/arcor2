import requests
import os
import json
import asyncio
from typing import Type, TypeVar

from dataclasses_jsonschema import ValidationError, JsonSchemaMixin

from arcor2.data.common import Project, Scene, ProjectSources, ObjectType, DataClassEncoder, IdDescList
from arcor2.exceptions import Arcor2Exception

URL = os.getenv("ARCOR2_PERSISTENT_STORAGE_URL", "http://127.0.0.1:5001")

# TODO logger
# TODO rename to PersistentStorage (and remove nodes/persistent_storage.py)
# TODO thread to poll changes? how to "detect" changes?

TIMEOUT = (0.1, 0.25)  # connect, read


class PersistentStorageClientException(Arcor2Exception):
    pass


T = TypeVar('T', bound=JsonSchemaMixin)


class PersistentStorageClient:

    def _post(self, url: str, data: JsonSchemaMixin):

        try:
            resp = requests.post(url, json=json.dumps(data, cls=DataClassEncoder), timeout=TIMEOUT)
            resp.raise_for_status()
        except requests.exceptions.RequestException as e:
            print(e)
            raise PersistentStorageClientException("Catastrophic error.")

    def _get(self, url: str, data_cls: Type[T]) -> T:

        try:
            resp = requests.get(url, timeout=TIMEOUT)
            resp.raise_for_status()
        except requests.exceptions.RequestException as e:
            print(e)
            raise PersistentStorageClientException("Catastrophic error.")

        try:
            data = json.loads(resp.text)
        except (json.JSONDecodeError, TypeError) as e:
            print(e)
            raise PersistentStorageClientException("Invalid JSON.")

        try:
            return data_cls.from_dict(data)
        except ValidationError as e:
            print(e)
            raise PersistentStorageClientException("Invalid data.")

    def get_projects(self) -> IdDescList:
        return self._get(f"{URL}/projects", IdDescList)

    def get_scenes(self) -> IdDescList:
        return self._get(f"{URL}/scenes", IdDescList)

    def get_project(self, project_id: str) -> Project:
        return self._get(f"{URL}/project/{project_id}", Project)

    def get_project_sources(self, project_id: str) -> ProjectSources:
        return self._get(f"{URL}/project/{project_id}/sources", ProjectSources)

    def get_scene(self, scene_id: str) -> Scene:
        return self._get(f"{URL}/scene/{scene_id}", Scene)

    def get_object_type(self, object_type_id: str) -> ObjectType:
        return self._get(f"{URL}/object_type/{object_type_id}", ObjectType)

    def get_object_type_ids(self) -> IdDescList:
        return self._get(f"{URL}/object_types", IdDescList)

    def update_project(self, project: Project) -> None:

        assert project.id
        self._post(f"{URL}/project", project)

    def update_scene(self, scene: Scene) -> None:

        assert scene.id
        self._post(f"{URL}/scene", scene)

    def update_project_sources(self, project_sources: ProjectSources) -> None:

        assert project_sources.id
        self._post(f"{URL}/project/sources", project_sources)

    def update_object_type(self, object_type: ObjectType) -> None:

        assert object_type.id
        self._post(f"{URL}/object_type", object_type)


loop = asyncio.get_event_loop()


class AioPersistentStorageClient:

    def __init__(self):

        self._cl = PersistentStorageClient()

    async def get_projects(self) -> IdDescList:
        return await loop.run_in_executor(None, self._cl.get_projects)

    async def get_scenes(self) -> IdDescList:
        return await loop.run_in_executor(None, self._cl.get_scenes)

    async def get_project(self, project_id: str) -> Project:
        return await loop.run_in_executor(None, self._cl.get_project, project_id)

    async def get_project_sources(self, project_id: str) -> ProjectSources:
        return await loop.run_in_executor(None, self._cl.get_project_sources, project_id)

    async def get_scene(self, scene_id: str) -> Scene:
        return await loop.run_in_executor(None, self._cl.get_scene, scene_id)

    async def get_object_type(self, object_type_id: str) -> ObjectType:
        return await loop.run_in_executor(None, self._cl.get_object_type, object_type_id)

    async def get_object_type_ids(self) -> IdDescList:
        return await loop.run_in_executor(None, self._cl.get_object_type_ids)

    async def update_project(self, project: Project):
        return await loop.run_in_executor(None, self._cl.update_project, project)

    async def update_scene(self, scene: Scene):
        return await loop.run_in_executor(None, self._cl.update_scene, scene)

    async def update_project_sources(self, project_sources: ProjectSources):
        return await loop.run_in_executor(None,
                                          self._cl.update_project_sources,
                                          project_sources)

    async def update_object_type(self, object_type: ObjectType):
        return await loop.run_in_executor(None, self._cl.update_object_type, object_type)
