import os
from datetime import datetime
from typing import Dict, List, Optional, Set

from arcor2 import rest
from arcor2.data.common import Asset, IdDesc, Project, ProjectParameter, ProjectSources, Scene, SceneObjectOverride
from arcor2.data.object_type import MODEL_MAPPING, Mesh, MeshList, MetaModel3d, Model, Model3dType, ObjectType
from arcor2.exceptions import Arcor2Exception
from arcor2.exceptions.helpers import handle
from arcor2.logging import get_logger

URL = os.getenv("ARCOR2_PROJECT_SERVICE_URL", "http://0.0.0.0:10000")

"""
Collection of functions to work with the Project service (0.10.0).

All functions raise ProjectServiceException when any failure happens.

"""

logger = get_logger("Project")


class ProjectServiceException(Arcor2Exception):
    pass


# ----------------------------------------------------------------------------------------------------------------------
# Assets
# ----------------------------------------------------------------------------------------------------------------------


@handle(ProjectServiceException, logger, message="Failed to list assets.")
def assets_ids() -> Set[str]:
    """Gets IDs of stored assets."""

    ret_list = rest.call(rest.Method.GET, f"{URL}/assets", list_return_type=str)
    ret_set = set(ret_list)
    assert len(ret_list) == len(ret_set), f"There is a duplicate asset ID in {ret_list}."

    return ret_set


@handle(ProjectServiceException, logger, message="Failed to update the asset.")
def update_asset(asset: Asset) -> None:
    """Adds or updates the asset."""

    rest.call(rest.Method.PUT, f"{URL}/assets", body=asset)
    assert asset.id in assets_ids()


@handle(ProjectServiceException, logger, message="Failed to get the asset.")
def get_asset(asset_id: str) -> Asset:
    """Gets the asset."""

    return rest.call(rest.Method.GET, f"{URL}/assets/{asset_id}", return_type=Asset)


@handle(ProjectServiceException, logger, message="Failed to delete the asset.")
def delete_asset(asset_id: str) -> None:
    """Deletes the asset."""

    rest.call(rest.Method.DELETE, f"{URL}/assets/{asset_id}")
    assert asset_id not in assets_ids()


# ----------------------------------------------------------------------------------------------------------------------
# Files
# ----------------------------------------------------------------------------------------------------------------------


@handle(ProjectServiceException, logger, message="Failed to list files.")
def files_ids() -> Set[str]:
    """Gets IDs of stored files."""

    ret_list = rest.call(rest.Method.GET, f"{URL}/files", list_return_type=str)
    ret_set = set(ret_list)
    assert len(ret_list) == len(ret_set), f"There is a duplicate file ID in {ret_list}."
    return ret_set


@handle(ProjectServiceException, logger, message="Failed to get the file.")
def save_file(file_id: str, path: str) -> None:
    """Saves the file to a given path."""

    rest.download(f"{URL}/files/{file_id}", path)
    assert os.path.isfile(path)


@handle(ProjectServiceException, logger, message="Failed to upload the file.")
def upload_file(file_id: str, file_content: bytes) -> None:
    """Uploads a file."""

    rest.call(rest.Method.PUT, f"{URL}/files/{file_id}", files={"file": file_content})
    assert file_id in files_ids()


@handle(ProjectServiceException, logger, message="Failed to delete the file.")
def delete_file(file_id: str) -> None:
    """Saves the file to a given path."""

    rest.call(rest.Method.DELETE, f"{URL}/files/{file_id}")
    assert file_id not in files_ids()


# ----------------------------------------------------------------------------------------------------------------------
# Models
# ----------------------------------------------------------------------------------------------------------------------


@handle(ProjectServiceException, logger, message="Failed to list models.")
def get_models() -> List[MetaModel3d]:
    return rest.call(rest.Method.GET, f"{URL}/models", list_return_type=MetaModel3d)


@handle(ProjectServiceException, logger, message="Failed to get the mesh.")
def get_mesh(mesh_id: str) -> Mesh:
    return rest.call(rest.Method.GET, f"{URL}/models/{mesh_id}/mesh", return_type=Mesh)


@handle(ProjectServiceException, logger, message="Failed to get list of meshes.")
def get_meshes() -> MeshList:
    return rest.call(rest.Method.GET, f"{URL}/models/meshes", list_return_type=Mesh)


@handle(ProjectServiceException, logger, message="Failed to get the model type.")
def get_model(model_id: str, model_type: Model3dType) -> Model:
    return rest.call(
        rest.Method.GET, f"{URL}/models/{model_id}/{model_type.value.lower()}", return_type=MODEL_MAPPING[model_type]
    )


@handle(ProjectServiceException, logger, message="Failed to add or update the model.")
def put_model(model: Model) -> None:
    rest.call(rest.Method.PUT, f"{URL}/models/{model.__class__.__name__.lower()}", body=model)


@handle(ProjectServiceException, logger, message="Failed to delete the model.")
def delete_model(model_id: str) -> None:
    rest.call(rest.Method.DELETE, f"{URL}/models/{model_id}")


# ----------------------------------------------------------------------------------------------------------------------
# ObjectParameters
# ----------------------------------------------------------------------------------------------------------------------


@handle(ProjectServiceException, logger, message="Failed to get project parameters.")
def get_object_parameters(project_id: str) -> List[SceneObjectOverride]:
    return rest.call(
        rest.Method.GET, f"{URL}/projects/{project_id}/object_parameters", list_return_type=SceneObjectOverride
    )


@handle(ProjectServiceException, logger, message="Failed to add or update project parameters.")
def update_object_parameters(project_id: str, parameters: List[SceneObjectOverride]) -> None:
    rest.call(rest.Method.GET, f"{URL}/projects/{project_id}/object_parameters", body=parameters)


# ----------------------------------------------------------------------------------------------------------------------
# ObjectTypes
# ----------------------------------------------------------------------------------------------------------------------


@handle(ProjectServiceException, logger, message="Failed to get the object type.")
def get_object_type(object_type_id: str) -> ObjectType:
    obj_type = rest.call(rest.Method.GET, f"{URL}/object_types/{object_type_id}", return_type=ObjectType)
    assert obj_type.modified, f"Project service returned object without 'modified': {obj_type.id}."
    return obj_type


@handle(ProjectServiceException, logger, message="Failed to list object types.")
def get_object_type_ids() -> List[IdDesc]:
    return rest.call(rest.Method.GET, f"{URL}/object_types", list_return_type=IdDesc)


@handle(ProjectServiceException, logger, message="Failed to add or update the object type.")
def update_object_type(object_type: ObjectType) -> datetime:

    assert object_type.id
    return datetime.fromisoformat(rest.call(rest.Method.PUT, f"{URL}/object_type", body=object_type, return_type=str))


@handle(ProjectServiceException, logger, message="Failed to delete the object type.")
def delete_object_type(object_type_id: str) -> None:
    rest.call(rest.Method.DELETE, f"{URL}/object_types/{object_type_id}")


# ----------------------------------------------------------------------------------------------------------------------
# Parameters
# ----------------------------------------------------------------------------------------------------------------------


@handle(ProjectServiceException, logger, message="Failed to get project parameters.")
def get_project_parameters(project_id: str) -> List[ProjectParameter]:
    return rest.call(rest.Method.GET, f"{URL}/projects/{project_id}/parameters", list_return_type=ProjectParameter)


@handle(ProjectServiceException, logger, message="Failed to add or update project parameters.")
def update_project_parameters(project_id: str, parameters: List[ProjectParameter]) -> datetime:
    return datetime.fromisoformat(
        rest.call(rest.Method.GET, f"{URL}/projects/{project_id}/parameters", body=parameters, return_type=str)
    )


# ----------------------------------------------------------------------------------------------------------------------
# Projects
# ----------------------------------------------------------------------------------------------------------------------


@handle(ProjectServiceException, logger, message="Failed to list projects.")
def get_projects() -> List[IdDesc]:
    return rest.call(rest.Method.GET, f"{URL}/projects", list_return_type=IdDesc)


@handle(ProjectServiceException, logger, message="Failed to get the project.")
def get_project(project_id: str) -> Project:
    return rest.call(rest.Method.GET, f"{URL}/projects/{project_id}", return_type=Project)


@handle(ProjectServiceException, logger, message="Failed to get the project sources.")
def get_project_sources(project_id: str) -> ProjectSources:
    return rest.call(rest.Method.GET, f"{URL}/projects/{project_id}/sources", return_type=ProjectSources)


@handle(ProjectServiceException, logger, message="Failed to add or update the project.")
def update_project(project: Project) -> datetime:

    assert project.id
    return datetime.fromisoformat(rest.call(rest.Method.PUT, f"{URL}/project", return_type=str, body=project))


@handle(ProjectServiceException, logger, message="Failed to add or update the project sources.")
def update_project_sources(project_sources: ProjectSources) -> None:

    assert project_sources.id
    rest.call(rest.Method.PUT, f"{URL}/sources", body=project_sources)


@handle(ProjectServiceException, logger, message="Failed to delete the project.")
def delete_project(project_id: str) -> None:
    rest.call(rest.Method.DELETE, f"{URL}/projects/{project_id}")


@handle(ProjectServiceException, logger, message="Failed to clone the project.")
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


@handle(ProjectServiceException, logger, message="Failed to list scenes.")
def get_scenes() -> List[IdDesc]:
    return rest.call(rest.Method.GET, f"{URL}/scenes", list_return_type=IdDesc)


@handle(ProjectServiceException, logger, message="Failed to get the scene.")
def get_scene(scene_id: str) -> Scene:
    return rest.call(rest.Method.GET, f"{URL}/scenes/{scene_id}", return_type=Scene)


@handle(ProjectServiceException, logger, message="Failed to add or update the scene.")
def update_scene(scene: Scene) -> datetime:

    assert scene.id
    return datetime.fromisoformat(rest.call(rest.Method.PUT, f"{URL}/scene", return_type=str, body=scene))


@handle(ProjectServiceException, logger, message="Failed to delete the scene.")
def delete_scene(scene_id: str) -> None:
    rest.call(rest.Method.DELETE, f"{URL}/scenes/{scene_id}")
