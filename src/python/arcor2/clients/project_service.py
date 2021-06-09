import os
from datetime import datetime
from typing import Dict, List, Optional

from arcor2 import rest
from arcor2.data.common import IdDesc, Project, ProjectParameter, ProjectSources, Scene, SceneObjectOverride
from arcor2.data.object_type import MODEL_MAPPING, Mesh, MeshList, MetaModel3d, Model, Model3dType, ObjectType
from arcor2.exceptions import Arcor2Exception
from arcor2.exceptions.helpers import handle

URL = os.getenv("ARCOR2_PROJECT_SERVICE_URL", "http://0.0.0.0:11000")

"""
Collection of functions to work with the Project service (0.8.0).

All functions raise ProjectServiceException when any failure happens.

"""


class ProjectServiceException(Arcor2Exception):
    pass


# ----------------------------------------------------------------------------------------------------------------------
# Models
# ----------------------------------------------------------------------------------------------------------------------


@handle(ProjectServiceException, message="Failed to list models.")
def get_models() -> List[MetaModel3d]:
    return rest.call(rest.Method.GET, f"{URL}/models/", list_return_type=MetaModel3d)


@handle(ProjectServiceException, message="Failed to get the mesh.")
def get_mesh(mesh_id: str) -> Mesh:
    return rest.call(rest.Method.GET, f"{URL}/models/{mesh_id}/mesh", return_type=Mesh)


@handle(ProjectServiceException, message="Failed to get list of meshes.")
def get_meshes() -> MeshList:
    return rest.call(rest.Method.GET, f"{URL}/models/meshes", list_return_type=Mesh)


@handle(ProjectServiceException, message="Failed to get the model type.")
def get_model(model_id: str, model_type: Model3dType) -> Model:
    return rest.call(
        rest.Method.GET, f"{URL}/models/{model_id}/{model_type.value.lower()}", return_type=MODEL_MAPPING[model_type]
    )


@handle(ProjectServiceException, message="Failed to add or update the model.")
def put_model(model: Model) -> None:
    rest.call(rest.Method.PUT, f"{URL}/models/{model.__class__.__name__.lower()}", body=model)


@handle(ProjectServiceException, message="Failed to delete the model.")
def delete_model(model_id: str) -> None:
    rest.call(rest.Method.DELETE, f"{URL}/models/{model_id}")


@handle(ProjectServiceException, message="Failed to get the mesh.")
def save_mesh_file(mesh_id: str, path: str) -> None:
    """Saves mesh file to a given path."""

    rest.download(f"{URL}/models/{mesh_id}/mesh/file", path)


@handle(ProjectServiceException, message="Failed to upload the mesh.")
def upload_mesh_file(mesh_id: str, file_content: bytes) -> None:
    """Upload a mesh file."""

    rest.call(rest.Method.PUT, f"{URL}/models/{mesh_id}/mesh/file", files={"file": file_content})


# ----------------------------------------------------------------------------------------------------------------------
# ObjectParameters
# ----------------------------------------------------------------------------------------------------------------------


@handle(ProjectServiceException, message="Failed to get project parameters.")
def get_object_parameters(project_id: str) -> List[SceneObjectOverride]:
    return rest.call(
        rest.Method.GET, f"{URL}/projects/{project_id}/object_parameters", list_return_type=SceneObjectOverride
    )


@handle(ProjectServiceException, message="Failed to add or update project parameters.")
def update_object_parameters(project_id: str, parameters: List[SceneObjectOverride]) -> None:
    rest.call(rest.Method.GET, f"{URL}/projects/{project_id}/object_parameters", body=parameters)


# ----------------------------------------------------------------------------------------------------------------------
# ObjectTypes
# ----------------------------------------------------------------------------------------------------------------------


@handle(ProjectServiceException, message="Failed to get the object type.")
def get_object_type(object_type_id: str) -> ObjectType:
    return rest.call(rest.Method.GET, f"{URL}/object_types/{object_type_id}", return_type=ObjectType)


@handle(ProjectServiceException, message="Failed to list object types.")
def get_object_type_ids() -> List[IdDesc]:
    return rest.call(rest.Method.GET, f"{URL}/object_types", list_return_type=IdDesc)


@handle(ProjectServiceException, message="Failed to add or update the object type.")
def update_object_type(object_type: ObjectType) -> datetime:

    assert object_type.id
    return datetime.fromisoformat(rest.call(rest.Method.PUT, f"{URL}/object_type", body=object_type, return_type=str))


@handle(ProjectServiceException, message="Failed to delete the object type.")
def delete_object_type(object_type_id: str) -> None:
    rest.call(rest.Method.DELETE, f"{URL}/object_types/{object_type_id}")


# ----------------------------------------------------------------------------------------------------------------------
# Parameters
# ----------------------------------------------------------------------------------------------------------------------


@handle(ProjectServiceException, message="Failed to get project parameters.")
def get_project_parameters(project_id: str) -> List[ProjectParameter]:
    return rest.call(rest.Method.GET, f"{URL}/projects/{project_id}/parameters", list_return_type=ProjectParameter)


@handle(ProjectServiceException, message="Failed to add or update project parameters.")
def update_project_parameters(project_id: str, parameters: List[ProjectParameter]) -> datetime:
    return datetime.fromisoformat(
        rest.call(rest.Method.GET, f"{URL}/projects/{project_id}/parameters", body=parameters, return_type=str)
    )


# ----------------------------------------------------------------------------------------------------------------------
# Projects
# ----------------------------------------------------------------------------------------------------------------------


@handle(ProjectServiceException, message="Failed to list projects.")
def get_projects() -> List[IdDesc]:
    return rest.call(rest.Method.GET, f"{URL}/projects", list_return_type=IdDesc)


@handle(ProjectServiceException, message="Failed to get the project.")
def get_project(project_id: str) -> Project:
    return rest.call(rest.Method.GET, f"{URL}/projects/{project_id}", return_type=Project)


@handle(ProjectServiceException, message="Failed to get the project sources.")
def get_project_sources(project_id: str) -> ProjectSources:
    return rest.call(rest.Method.GET, f"{URL}/projects/{project_id}/sources", return_type=ProjectSources)


@handle(ProjectServiceException, message="Failed to add or update the project.")
def update_project(project: Project) -> datetime:

    assert project.id
    return datetime.fromisoformat(rest.call(rest.Method.PUT, f"{URL}/project", return_type=str, body=project))


@handle(ProjectServiceException, message="Failed to add or update the project sources.")
def update_project_sources(project_sources: ProjectSources) -> None:

    assert project_sources.id
    rest.call(rest.Method.PUT, f"{URL}/sources", body=project_sources)


@handle(ProjectServiceException, message="Failed to delete the project.")
def delete_project(project_id: str) -> None:
    rest.call(rest.Method.DELETE, f"{URL}/projects/{project_id}")


@handle(ProjectServiceException, message="Failed to clone the project.")
def clone_project(
    project_id: str, new_project_name: str, new_description: Optional[str] = None, new_project_id: Optional[str] = None
) -> Project:

    if not new_project_id:
        new_project_id = Project.uid()

    params: Dict[str, str] = {
        "project_id": project_id,
        "new_project_name": new_project_name,
        "new_project_id": new_project_id,
    }

    if new_description:
        params["new_description"] = new_description

    return rest.call(rest.Method.PUT, f"{URL}/projects/close", params=params, return_type=Project)


# ----------------------------------------------------------------------------------------------------------------------
# Scenes
# ----------------------------------------------------------------------------------------------------------------------


@handle(ProjectServiceException, message="Failed to list scenes.")
def get_scenes() -> List[IdDesc]:
    return rest.call(rest.Method.GET, f"{URL}/scenes", list_return_type=IdDesc)


@handle(ProjectServiceException, message="Failed to get the scene.")
def get_scene(scene_id: str) -> Scene:
    return rest.call(rest.Method.GET, f"{URL}/scenes/{scene_id}", return_type=Scene)


@handle(ProjectServiceException, message="Failed to add or update the scene.")
def update_scene(scene: Scene) -> datetime:

    assert scene.id
    return datetime.fromisoformat(rest.call(rest.Method.PUT, f"{URL}/scene", return_type=str, body=scene))


@handle(ProjectServiceException, message="Failed to delete the scene.")
def delete_scene(scene_id: str) -> None:
    rest.call(rest.Method.DELETE, f"{URL}/scenes/{scene_id}")
