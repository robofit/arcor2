import requests
import os
import json
import asyncio
from typing import Type, TypeVar, Dict, Callable

from dataclasses_jsonschema import ValidationError, JsonSchemaMixin

from arcor2.data.common import Project, Scene, ProjectSources, IdDescList
from arcor2.data.object_type import ObjectType, Models, MODEL_MAPPING, ModelTypeEnum
from arcor2.exceptions import Arcor2Exception
from arcor2.helpers import camel_case_to_snake_case, snake_case_to_camel_case

URL = os.getenv("ARCOR2_PERSISTENT_STORAGE_URL", "http://127.0.0.1:11000")

# TODO logger
# TODO rename to PersistentStorage (and remove nodes/persistent_storage.py)
# TODO thread to poll changes? how to "detect" changes?

TIMEOUT = (1.0, 1.0)  # connect, read


class PersistentStorageException(Arcor2Exception):
    pass


T = TypeVar('T', bound=JsonSchemaMixin)


def convert_keys(d: Dict, func: Callable[[str], str]) -> Dict:

    new = {}
    for k, v in d.items():
        if isinstance(v, dict):
            v = convert_keys(v, func)
        elif isinstance(v, list):
            for idx in range(len(v)):
                v[idx] = convert_keys(v[idx], func)
        new[func(k)] = v
    return new


def remove_none_values(d: Dict) -> None:  # temporary workaround for a bug in persistent storage

    to_delete = []

    for k, v in d.items():

        if v is None:
            to_delete.append(k)
        elif isinstance(v, dict):
            remove_none_values(v)
        elif isinstance(v, list):
            for l in v:
                remove_none_values(l)

    for td in to_delete:
        del d[td]


class PersistentStorage:

    def _handle_response(self, resp):

        try:
            resp.raise_for_status()
        except requests.exceptions.RequestException as e:
            print(e)
            raise PersistentStorageException(f"Status code: {resp.status_code}, "
                                             f"body: {json.loads(resp.content)}.")

    def _post(self, url: str, data: JsonSchemaMixin, op=requests.post) -> None:

        d = convert_keys(data.to_dict(), snake_case_to_camel_case)

        try:
            resp = op(url, data=json.dumps(d), timeout=TIMEOUT, headers={'Content-Type': 'application/json'})
        except requests.exceptions.RequestException as e:
            print(e)
            raise PersistentStorageException(f"Catastrophic error: {e}")

        self._handle_response(resp)

    def _get(self, url: str, data_cls: Type[T]) -> T:

        try:
            resp = requests.get(url, timeout=TIMEOUT)
        except requests.exceptions.RequestException as e:
            print(e)
            raise PersistentStorageException(f"Catastrophic error: {e}")

        self._handle_response(resp)

        try:
            data = json.loads(resp.text)
        except (json.JSONDecodeError, TypeError) as e:
            print(e)
            raise PersistentStorageException("Invalid JSON.")

        data = convert_keys(data, camel_case_to_snake_case)
        remove_none_values(data)

        try:
            return data_cls.from_dict(data)
        except ValidationError as e:
            print(f'{data_cls.__name__}: validation error "{e}" while parsing "{data}".')
            raise PersistentStorageException("Invalid data.")

    def get_model(self, model_id: str, model_type: ModelTypeEnum) -> Models:
        return self._get(f"{URL}/models/{model_id}/{model_type.value}", MODEL_MAPPING[model_type])

    def put_model(self, model: Models) -> None:
        self._post(f"{URL}/models/{model.__class__.__name__.lower()}", model, op=requests.put)

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


class AioPersistentStorage:

    def __init__(self):

        self._cl = PersistentStorage()

    async def get_model(self, model_id: str, model_type: str) -> Models:
        return await loop.run_in_executor(None, self._cl.get_model, model_id, model_type)

    async def put_model(self, model: Models):
        return await loop.run_in_executor(None, self._cl.put_model, model)

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
