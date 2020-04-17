import os

from arcor2.data.common import Project, Scene, ProjectSources, IdDescList
from arcor2.data.object_type import ObjectType, Models, MODEL_MAPPING, Model3dType, Mesh, MeshList
from arcor2.data.services import ServiceType
from arcor2.exceptions import Arcor2Exception
from arcor2 import rest

URL = os.getenv("ARCOR2_PERSISTENT_STORAGE_URL", "http://0.0.0.0:11000")

# TODO thread to poll changes? how to "detect" changes?


class PersistentStorageException(Arcor2Exception):
    pass


@rest.handle_exceptions(PersistentStorageException)
def get_mesh(mesh_id) -> Mesh:
    return rest.get(f"{URL}/models/{mesh_id}/mesh", Mesh)


@rest.handle_exceptions(PersistentStorageException)
def get_meshes() -> MeshList:
    return rest.get_list(f"{URL}/models/meshes", Mesh)


@rest.handle_exceptions(PersistentStorageException)
def get_model(model_id: str, model_type: Model3dType) -> Models:
    return rest.get(f"{URL}/models/{model_id}/{model_type.value}", MODEL_MAPPING[model_type])


@rest.handle_exceptions(PersistentStorageException)
def put_model(model: Models) -> None:
    rest.put(f"{URL}/models/{model.__class__.__name__.lower()}", model)


@rest.handle_exceptions(PersistentStorageException)
def get_projects() -> IdDescList:
    return rest.get(f"{URL}/projects", IdDescList)


@rest.handle_exceptions(PersistentStorageException)
def get_scenes() -> IdDescList:
    return rest.get(f"{URL}/scenes", IdDescList)


@rest.handle_exceptions(PersistentStorageException)
def get_project(project_id: str) -> Project:
    return rest.get(f"{URL}/project/{project_id}", Project)


@rest.handle_exceptions(PersistentStorageException)
def get_project_sources(project_id: str) -> ProjectSources:
    return rest.get(f"{URL}/project/{project_id}/sources", ProjectSources)


@rest.handle_exceptions(PersistentStorageException)
def get_scene(scene_id: str) -> Scene:
    return rest.get(f"{URL}/scene/{scene_id}", Scene)


@rest.handle_exceptions(PersistentStorageException)
def get_object_type(object_type_id: str) -> ObjectType:
    return rest.get(f"{URL}/object_types/{object_type_id}", ObjectType)


@rest.handle_exceptions(PersistentStorageException)
def get_service_type(service_type_id: str) -> ServiceType:
    return rest.get(f"{URL}/service_type/{service_type_id}", ServiceType)


@rest.handle_exceptions(PersistentStorageException)
def get_object_type_ids() -> IdDescList:
    return rest.get(f"{URL}/object_types", IdDescList)


@rest.handle_exceptions(PersistentStorageException)
def get_service_type_ids() -> IdDescList:
    return rest.get(f"{URL}/service_types", IdDescList)


@rest.handle_exceptions(PersistentStorageException)
def update_project(project: Project) -> None:

    assert project.id
    rest.put(f"{URL}/project", project)


@rest.handle_exceptions(PersistentStorageException)
def update_scene(scene: Scene) -> None:

    assert scene.id
    rest.put(f"{URL}/scene", scene)


@rest.handle_exceptions(PersistentStorageException)
def update_project_sources(project_sources: ProjectSources) -> None:

    assert project_sources.id
    rest.post(f"{URL}/project/sources", project_sources)


@rest.handle_exceptions(PersistentStorageException)
def update_object_type(object_type: ObjectType) -> None:

    assert object_type.id
    rest.put(f"{URL}/object_type", object_type)


@rest.handle_exceptions(PersistentStorageException)
def update_service_type(service_type: ServiceType) -> None:

    assert service_type.id
    rest.put(f"{URL}/service_type", service_type)


@rest.handle_exceptions(PersistentStorageException)
def delete_scene(scene_id: str) -> None:
    return rest.delete(f"{URL}/scene/{scene_id}")


@rest.handle_exceptions(PersistentStorageException)
def delete_project(project_id: str) -> None:
    return rest.delete(f"{URL}/project/{project_id}")
