from datetime import datetime

from arcor2.clients import project_service
from arcor2.clients.project_service import ProjectServiceException  # noqa
from arcor2.data.common import IdDesc, Project, ProjectSources, Scene
from arcor2.data.object_type import Mesh, MeshList, Model, Model3dType, ObjectType
from arcor2.helpers import run_in_executor


async def get_mesh(mesh_id: str) -> Mesh:
    return await run_in_executor(project_service.get_mesh, mesh_id)


async def get_meshes() -> MeshList:
    return await run_in_executor(project_service.get_meshes)


async def get_model(model_id: str, model_type: Model3dType) -> Model:
    return await run_in_executor(project_service.get_model, model_id, model_type)


async def put_model(model: Model) -> None:
    await run_in_executor(project_service.put_model, model)


async def delete_model(model_id: str) -> None:
    await run_in_executor(project_service.delete_model, model_id)


async def get_projects() -> list[IdDesc]:
    return await run_in_executor(project_service.get_projects)


async def get_scenes() -> list[IdDesc]:
    return await run_in_executor(project_service.get_scenes)


async def get_project(project_id: str) -> Project:
    return await run_in_executor(project_service.get_project, project_id)


async def get_project_sources(project_id: str) -> ProjectSources:
    return await run_in_executor(project_service.get_project_sources, project_id)


async def get_scene(scene_id: str) -> Scene:
    return await run_in_executor(project_service.get_scene, scene_id)


async def get_object_type(object_type_id: str) -> ObjectType:
    return await run_in_executor(project_service.get_object_type, object_type_id)


async def get_object_type_ids() -> list[IdDesc]:
    return await run_in_executor(project_service.get_object_type_ids)


async def update_project(project: Project) -> datetime:
    return await run_in_executor(project_service.update_project, project)


async def update_scene(scene: Scene) -> datetime:
    return await run_in_executor(project_service.update_scene, scene)


async def update_project_sources(project_sources: ProjectSources) -> None:
    await run_in_executor(project_service.update_project_sources, project_sources)


async def update_object_type(object_type: ObjectType) -> datetime:
    return await run_in_executor(project_service.update_object_type, object_type)


async def delete_object_type(object_type_id: str) -> None:
    await run_in_executor(project_service.delete_object_type, object_type_id)


async def delete_scene(scene_id: str) -> None:
    await run_in_executor(project_service.delete_scene, scene_id)


async def delete_project(project_id: str) -> None:
    await run_in_executor(project_service.delete_project, project_id)
