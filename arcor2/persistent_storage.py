import requests
import os
import json
import asyncio
from typing import Type, TypeVar, Dict, Callable, List, Union, Any

from dataclasses_jsonschema import ValidationError, JsonSchemaMixin

from arcor2.data.common import Project, Scene, ProjectSources, IdDescList
from arcor2.data.object_type import ObjectType, Models, MODEL_MAPPING, ModelTypeEnum, Mesh, MeshList
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


def convert_keys(d: Union[Dict, List], func: Callable[[str], str]) -> Union[Dict, List]:

    if isinstance(d, dict):
        new_dict = {}
        for k, v in d.items():
            new_dict[func(k)] = convert_keys(v, func)
        return new_dict
    elif isinstance(d, list):
        new_list: List[Any] = []
        for dd in d:
            new_list.append(convert_keys(dd, func))
        return new_list

    return d


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

    def _get_data(self, url: str) -> Union[Dict, List]:

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

        return convert_keys(data, camel_case_to_snake_case)

    def _get_list(self, url: str, data_cls: Type[T]) -> List[T]:

        data = self._get_data(url)

        ret: List[T] = []

        for val in data:
            try:
                ret.append(data_cls.from_dict(val))
            except ValidationError as e:
                print(f'{data_cls.__name__}: validation error "{e}" while parsing "{data}".')
                raise PersistentStorageException("Invalid data.")

        return ret

    def _get(self, url: str, data_cls: Type[T]) -> T:

        data = self._get_data(url)

        assert isinstance(data, dict)

        try:
            return data_cls.from_dict(data)
        except ValidationError as e:
            print(f'{data_cls.__name__}: validation error "{e}" while parsing "{data}".')
            raise PersistentStorageException("Invalid data.")

    def _download(self, url: str, path: str):

        # TODO check content type

        r = requests.get(url, allow_redirects=True)
        with open(path, 'wb') as file:
            file.write(r.content)

    def publish_project(self, project_id: str, path: str):
        self._download(f"{URL}/project/{project_id}/publish", path)

    def get_mesh(self, mesh_id) -> Mesh:
        return self._get(f"{URL}/models/{mesh_id}/mesh", Mesh)

    def get_meshes(self) -> MeshList:
        return self._get_list(f"{URL}/models/meshes", Mesh)

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
        return self._get(f"{URL}/object_types/{object_type_id}", ObjectType)

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

    async def publish_project(self, project_id: str, path: str) -> None:
        return await loop.run_in_executor(None, self._cl.publish_project, project_id, path)

    async def get_mesh(self, mesh_id: str) -> Mesh:
        return await loop.run_in_executor(None, self._cl.get_mesh, mesh_id)

    async def get_meshes(self) -> MeshList:
        return await loop.run_in_executor(None, self._cl.get_meshes)

    async def get_model(self, model_id: str, model_type: ModelTypeEnum) -> Models:
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
