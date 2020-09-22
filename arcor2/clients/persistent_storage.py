import os
from datetime import datetime

from arcor2 import rest
from arcor2.data.common import IdDescList, Project, ProjectSources, Scene
from arcor2.data.object_type import MODEL_MAPPING, Mesh, MeshList, Model3dType, Models, ObjectType
from arcor2.exceptions import Arcor2Exception

URL = os.getenv("ARCOR2_PERSISTENT_STORAGE_URL", "http://0.0.0.0:11000")

# TODO thread to poll changes? how to "detect" changes?


class PersistentStorageException(Arcor2Exception):
    pass


@rest.handle_exceptions(PersistentStorageException)
def get_mesh(mesh_id: str) -> Mesh:
    return rest.get(f"{URL}/models/{mesh_id}/mesh", Mesh)


@rest.handle_exceptions(PersistentStorageException)
def get_meshes() -> MeshList:
    return rest.get_list(f"{URL}/models/meshes", Mesh)


@rest.handle_exceptions(PersistentStorageException)
def get_model(model_id: str, model_type: Model3dType) -> Models:
    return rest.get(f"{URL}/models/{model_id}/{model_type.value.lower()}", MODEL_MAPPING[model_type])


@rest.handle_exceptions(PersistentStorageException)
def put_model(model: Models) -> None:
    rest.put(f"{URL}/models/{model.__class__.__name__.lower()}", model)


@rest.handle_exceptions(PersistentStorageException)
def delete_model(model_id: str) -> None:
    rest.delete(f"{URL}/models/{model_id}")


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
def get_object_type_ids() -> IdDescList:
    return rest.get(f"{URL}/object_types", IdDescList)


@rest.handle_exceptions(PersistentStorageException)
def update_project(project: Project) -> datetime:

    assert project.id
    return datetime.fromisoformat(rest.put_returning_primitive(f"{URL}/project", str, project))


@rest.handle_exceptions(PersistentStorageException)
def update_scene(scene: Scene) -> datetime:

    assert scene.id
    return datetime.fromisoformat(rest.put_returning_primitive(f"{URL}/scene", str, scene))


@rest.handle_exceptions(PersistentStorageException)
def update_project_sources(project_sources: ProjectSources) -> None:

    assert project_sources.id
    rest.post(f"{URL}/project/sources", project_sources)


@rest.handle_exceptions(PersistentStorageException)
def update_object_type(object_type: ObjectType) -> None:

    assert object_type.id
    rest.put(f"{URL}/object_type", object_type)


@rest.handle_exceptions(PersistentStorageException)
def delete_object_type(object_type_id: str) -> None:
    rest.delete(f"{URL}/object_type/{object_type_id}")


@rest.handle_exceptions(PersistentStorageException)
def delete_scene(scene_id: str) -> None:
    rest.delete(f"{URL}/scene/{scene_id}")


@rest.handle_exceptions(PersistentStorageException)
def delete_project(project_id: str) -> None:
    rest.delete(f"{URL}/project/{project_id}")
