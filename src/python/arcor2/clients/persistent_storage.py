import os
from datetime import datetime

from arcor2 import rest
from arcor2.data.common import IdDescList, Project, ProjectSources, Scene
from arcor2.data.object_type import MODEL_MAPPING, Mesh, MeshList, Model, Model3dType, ObjectType
from arcor2.exceptions import Arcor2Exception

URL = os.getenv("ARCOR2_PERSISTENT_STORAGE_URL", "http://0.0.0.0:11000")

# TODO thread to poll changes? how to "detect" changes?


class PersistentStorageException(Arcor2Exception):
    pass


@rest.handle_exceptions(PersistentStorageException)
def get_mesh(mesh_id: str) -> Mesh:
    return rest.call(rest.Method.GET, f"{URL}/models/{mesh_id}/mesh", return_type=Mesh)


@rest.handle_exceptions(PersistentStorageException)
def get_meshes() -> MeshList:
    return rest.call(rest.Method.GET, f"{URL}/models/meshes", list_return_type=Mesh)


@rest.handle_exceptions(PersistentStorageException)
def get_model(model_id: str, model_type: Model3dType) -> Model:
    return rest.call(
        rest.Method.GET, f"{URL}/models/{model_id}/{model_type.value.lower()}", return_type=MODEL_MAPPING[model_type]
    )


@rest.handle_exceptions(PersistentStorageException)
def put_model(model: Model) -> None:
    rest.call(rest.Method.PUT, f"{URL}/models/{model.__class__.__name__.lower()}", body=model)


@rest.handle_exceptions(PersistentStorageException)
def delete_model(model_id: str) -> None:
    rest.call(rest.Method.DELETE, f"{URL}/models/{model_id}")


@rest.handle_exceptions(PersistentStorageException)
def get_projects() -> IdDescList:
    return rest.call(rest.Method.GET, f"{URL}/projects", return_type=IdDescList)


@rest.handle_exceptions(PersistentStorageException)
def get_scenes() -> IdDescList:
    return rest.call(rest.Method.GET, f"{URL}/scenes", return_type=IdDescList)


@rest.handle_exceptions(PersistentStorageException)
def get_project(project_id: str) -> Project:
    return rest.call(rest.Method.GET, f"{URL}/project/{project_id}", return_type=Project)


@rest.handle_exceptions(PersistentStorageException)
def get_project_sources(project_id: str) -> ProjectSources:
    return rest.call(rest.Method.GET, f"{URL}/project/{project_id}/sources", return_type=ProjectSources)


@rest.handle_exceptions(PersistentStorageException)
def get_scene(scene_id: str) -> Scene:
    return rest.call(rest.Method.GET, f"{URL}/scene/{scene_id}", return_type=Scene)


@rest.handle_exceptions(PersistentStorageException)
def get_object_type(object_type_id: str) -> ObjectType:
    return rest.call(rest.Method.GET, f"{URL}/object_types/{object_type_id}", return_type=ObjectType)


@rest.handle_exceptions(PersistentStorageException)
def get_object_type_ids() -> IdDescList:
    return rest.call(rest.Method.GET, f"{URL}/object_types", return_type=IdDescList)


@rest.handle_exceptions(PersistentStorageException)
def update_project(project: Project) -> datetime:

    assert project.id
    return datetime.fromisoformat(rest.call(rest.Method.PUT, f"{URL}/project", return_type=str, body=project))


@rest.handle_exceptions(PersistentStorageException)
def update_scene(scene: Scene) -> datetime:

    assert scene.id
    return datetime.fromisoformat(rest.call(rest.Method.PUT, f"{URL}/scene", return_type=str, body=scene))


@rest.handle_exceptions(PersistentStorageException)
def update_project_sources(project_sources: ProjectSources) -> None:

    assert project_sources.id
    rest.call(rest.Method.POST, f"{URL}/project/sources", body=project_sources)


@rest.handle_exceptions(PersistentStorageException)
def update_object_type(object_type: ObjectType) -> None:

    assert object_type.id
    rest.call(rest.Method.PUT, f"{URL}/object_type", body=object_type)


@rest.handle_exceptions(PersistentStorageException)
def delete_object_type(object_type_id: str) -> None:
    rest.call(rest.Method.DELETE, f"{URL}/object_type/{object_type_id}")


@rest.handle_exceptions(PersistentStorageException)
def delete_scene(scene_id: str) -> None:
    rest.call(rest.Method.DELETE, f"{URL}/scene/{scene_id}")


@rest.handle_exceptions(PersistentStorageException)
def delete_project(project_id: str) -> None:
    rest.call(rest.Method.DELETE, f"{URL}/project/{project_id}")


@rest.handle_exceptions(PersistentStorageException)
def save_mesh_file(mesh_id: str, path: str) -> None:
    """Saves mesh file to a given path."""

    rest.download(f"{URL}/models/{mesh_id}/mesh/file", path)
