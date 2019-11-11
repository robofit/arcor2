import os

from arcor2.data.common import Project, Scene, ProjectSources, IdDescList
from arcor2.data.object_type import ObjectType, Models, MODEL_MAPPING, ModelTypeEnum, Mesh, MeshList
from arcor2.exceptions import Arcor2Exception
from arcor2.helpers import run_in_executor
from arcor2 import rest

URL = os.getenv("ARCOR2_PERSISTENT_STORAGE_URL", "http://127.0.0.1:11000")

# TODO decorator to catch rest.RestException and fire PersistentStorageException instead
# TODO logger
# TODO thread to poll changes? how to "detect" changes?


class PersistentStorageException(Arcor2Exception):
    pass


class PersistentStorage:

    def publish_project(self, project_id: str, path: str) -> None:
        rest.download(f"{URL}/project/{project_id}/publish", path)

    def get_mesh(self, mesh_id) -> Mesh:
        return rest.get(f"{URL}/models/{mesh_id}/mesh", Mesh)

    def get_meshes(self) -> MeshList:
        return rest.get_list(f"{URL}/models/meshes", Mesh)

    def get_model(self, model_id: str, model_type: ModelTypeEnum) -> Models:
        return rest.get(f"{URL}/models/{model_id}/{model_type.value}", MODEL_MAPPING[model_type])

    def put_model(self, model: Models) -> None:
        rest.put(f"{URL}/models/{model.__class__.__name__.lower()}", model)

    def get_projects(self) -> IdDescList:
        return rest.get(f"{URL}/projects", IdDescList)

    def get_scenes(self) -> IdDescList:
        return rest.get(f"{URL}/scenes", IdDescList)

    def get_project(self, project_id: str) -> Project:
        return rest.get(f"{URL}/project/{project_id}", Project)

    def get_project_sources(self, project_id: str) -> ProjectSources:
        return rest.get(f"{URL}/project/{project_id}/sources", ProjectSources)

    def get_scene(self, scene_id: str) -> Scene:
        return rest.get(f"{URL}/scene/{scene_id}", Scene)

    def get_object_type(self, object_type_id: str) -> ObjectType:
        return rest.get(f"{URL}/object_types/{object_type_id}", ObjectType)

    def get_object_type_ids(self) -> IdDescList:
        return rest.get(f"{URL}/object_types", IdDescList)

    def update_project(self, project: Project) -> None:

        assert project.id
        rest.post(f"{URL}/project", project)

    def update_scene(self, scene: Scene) -> None:

        assert scene.id
        rest.post(f"{URL}/scene", scene)

    def update_project_sources(self, project_sources: ProjectSources) -> None:

        assert project_sources.id
        rest.post(f"{URL}/project/sources", project_sources)

    def update_object_type(self, object_type: ObjectType) -> None:

        assert object_type.id
        rest.post(f"{URL}/object_type", object_type)


class AioPersistentStorage:

    def __init__(self) -> None:

        self._cl = PersistentStorage()

    async def publish_project(self, project_id: str, path: str) -> None:
        return await run_in_executor(self._cl.publish_project, project_id, path)

    async def get_mesh(self, mesh_id: str) -> Mesh:
        return await run_in_executor(self._cl.get_mesh, mesh_id)

    async def get_meshes(self) -> MeshList:
        return await run_in_executor(self._cl.get_meshes)

    async def get_model(self, model_id: str, model_type: ModelTypeEnum) -> Models:
        return await run_in_executor(self._cl.get_model, model_id, model_type)

    async def put_model(self, model: Models) -> None:
        await run_in_executor(self._cl.put_model, model)

    async def get_projects(self) -> IdDescList:
        return await run_in_executor(self._cl.get_projects)

    async def get_scenes(self) -> IdDescList:
        return await run_in_executor(self._cl.get_scenes)

    async def get_project(self, project_id: str) -> Project:
        return await run_in_executor(self._cl.get_project, project_id)

    async def get_project_sources(self, project_id: str) -> ProjectSources:
        return await run_in_executor(self._cl.get_project_sources, project_id)

    async def get_scene(self, scene_id: str) -> Scene:
        return await run_in_executor(self._cl.get_scene, scene_id)

    async def get_object_type(self, object_type_id: str) -> ObjectType:
        return await run_in_executor(self._cl.get_object_type, object_type_id)

    async def get_object_type_ids(self) -> IdDescList:
        return await run_in_executor(self._cl.get_object_type_ids)

    async def update_project(self, project: Project) -> None:
        await run_in_executor(self._cl.update_project, project)

    async def update_scene(self, scene: Scene) -> None:
        await run_in_executor(self._cl.update_scene, scene)

    async def update_project_sources(self, project_sources: ProjectSources) -> None:
        await run_in_executor(self._cl.update_project_sources, project_sources)

    async def update_object_type(self, object_type: ObjectType) -> None:
        await run_in_executor(self._cl.update_object_type, object_type)
