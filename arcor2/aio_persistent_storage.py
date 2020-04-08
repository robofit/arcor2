from arcor2.data.common import Project, Scene, ProjectSources, IdDescList
from arcor2.data.object_type import ObjectType, Models, Model3dType, Mesh, MeshList
from arcor2.data.services import ServiceType
from arcor2.helpers import run_in_executor
from arcor2 import persistent_storage
from arcor2.persistent_storage import PersistentStorageException  # noqa


async def get_mesh(mesh_id: str) -> Mesh:
    return await run_in_executor(persistent_storage.get_mesh, mesh_id)


async def get_meshes() -> MeshList:
    return await run_in_executor(persistent_storage.get_meshes)


async def get_model(model_id: str, model_type: Model3dType) -> Models:
    return await run_in_executor(persistent_storage.get_model, model_id, model_type)


async def put_model(model: Models) -> None:
    await run_in_executor(persistent_storage.put_model, model)


async def get_projects() -> IdDescList:
    return await run_in_executor(persistent_storage.get_projects)


async def get_scenes() -> IdDescList:
    return await run_in_executor(persistent_storage.get_scenes)


async def get_project(project_id: str) -> Project:
    return await run_in_executor(persistent_storage.get_project, project_id)


async def get_project_sources(project_id: str) -> ProjectSources:
    return await run_in_executor(persistent_storage.get_project_sources, project_id)


async def get_scene(scene_id: str) -> Scene:
    return await run_in_executor(persistent_storage.get_scene, scene_id)


async def get_object_type(object_type_id: str) -> ObjectType:
    return await run_in_executor(persistent_storage.get_object_type, object_type_id)


async def get_service_type(service_type_id: str) -> ServiceType:
    return await run_in_executor(persistent_storage.get_service_type, service_type_id)


async def get_object_type_ids() -> IdDescList:
    return await run_in_executor(persistent_storage.get_object_type_ids)


async def get_service_type_ids() -> IdDescList:
    return await run_in_executor(persistent_storage.get_service_type_ids)


async def update_project(project: Project) -> None:
    await run_in_executor(persistent_storage.update_project, project)


async def update_scene(scene: Scene) -> None:
    await run_in_executor(persistent_storage.update_scene, scene)


async def update_project_sources(project_sources: ProjectSources) -> None:
    await run_in_executor(persistent_storage.update_project_sources, project_sources)


async def update_object_type(object_type: ObjectType) -> None:
    await run_in_executor(persistent_storage.update_object_type, object_type)


async def update_service_type(service_type: ServiceType) -> None:
    await run_in_executor(persistent_storage.update_service_type, service_type)


async def delete_scene(scene_id: str) -> None:
    await run_in_executor(persistent_storage.delete_scene, scene_id)


async def delete_project(project_id: str) -> None:
    await run_in_executor(persistent_storage.delete_project, project_id)
