import os
from datetime import datetime

from dateutil.parser import parse

from arcor2 import rest
from arcor2.data.common import IdDesc, Project, ProjectParameter, ProjectSources, Scene, SceneObjectOverride
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
# Models
# ----------------------------------------------------------------------------------------------------------------------


@handle(ProjectServiceException, logger, message="Failed to list models.")
def get_models() -> list[MetaModel3d]:
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
def get_object_parameters(project_id: str) -> list[SceneObjectOverride]:
    return rest.call(
        rest.Method.GET, f"{URL}/projects/{project_id}/object-parameters", list_return_type=SceneObjectOverride
    )


@handle(ProjectServiceException, logger, message="Failed to add or update project parameters.")
def update_object_parameters(project_id: str, parameters: list[SceneObjectOverride]) -> None:
    rest.call(rest.Method.GET, f"{URL}/projects/{project_id}/object-parameters", body=parameters)


# ----------------------------------------------------------------------------------------------------------------------
# ObjectTypes
# ----------------------------------------------------------------------------------------------------------------------


@handle(ProjectServiceException, logger, message="Failed to get the object type.")
def get_object_type(object_type_id: str) -> ObjectType:
    obj_type = rest.call(rest.Method.GET, f"{URL}/object-types/{object_type_id}", return_type=ObjectType)
    assert obj_type.modified, f"Project service returned object without 'modified': {obj_type.id}."
    return obj_type


@handle(ProjectServiceException, logger, message="Failed to list object types.")
def get_object_type_ids() -> list[IdDesc]:
    return rest.call(rest.Method.GET, f"{URL}/object-types", list_return_type=IdDesc)


@handle(ProjectServiceException, logger, message="Failed to add or update the object type.")
def update_object_type(object_type: ObjectType) -> datetime:

    assert object_type.id
    return parse(rest.call(rest.Method.PUT, f"{URL}/object-types", body=object_type, return_type=str))


@handle(ProjectServiceException, logger, message="Failed to delete the object type.")
def delete_object_type(object_type_id: str) -> None:
    rest.call(rest.Method.DELETE, f"{URL}/object-types/{object_type_id}")


# ----------------------------------------------------------------------------------------------------------------------
# Parameters
# ----------------------------------------------------------------------------------------------------------------------


@handle(ProjectServiceException, logger, message="Failed to get project parameters.")
def get_project_parameters(project_id: str) -> list[ProjectParameter]:
    return rest.call(rest.Method.GET, f"{URL}/projects/{project_id}/parameters", list_return_type=ProjectParameter)


@handle(ProjectServiceException, logger, message="Failed to add or update project parameters.")
def update_project_parameters(project_id: str, parameters: list[ProjectParameter]) -> datetime:
    return parse(
        rest.call(rest.Method.GET, f"{URL}/projects/{project_id}/parameters", body=parameters, return_type=str)
    )


# ----------------------------------------------------------------------------------------------------------------------
# Projects
# ----------------------------------------------------------------------------------------------------------------------


@handle(ProjectServiceException, logger, message="Failed to list projects.")
def get_projects() -> list[IdDesc]:
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
    return parse(rest.call(rest.Method.PUT, f"{URL}/projects", return_type=str, body=project))


@handle(ProjectServiceException, logger, message="Failed to add or update the project sources.")
def update_project_sources(project_sources: ProjectSources) -> None:

    assert project_sources.id
    rest.call(rest.Method.PUT, f"{URL}/projects/sources", body=project_sources)


@handle(ProjectServiceException, logger, message="Failed to delete the project.")
def delete_project(project_id: str) -> None:
    rest.call(rest.Method.DELETE, f"{URL}/projects/{project_id}")


@handle(ProjectServiceException, logger, message="Failed to clone the project.")
def clone_project(
    project_id: str, new_project_name: str, new_description: None | str = None, new_project_id: None | str = None
) -> Project:

    if not new_project_id:
        new_project_id = Project.uid()

    params: dict[str, str] = {
        "project_id": project_id,
        "new_project_name": new_project_name,
        "new_project_id": new_project_id,
    }

    if new_description:
        params["new_description"] = new_description

    return rest.call(rest.Method.PUT, f"{URL}/projects/clone", params=params, return_type=Project)


# ----------------------------------------------------------------------------------------------------------------------
# Scenes
# ----------------------------------------------------------------------------------------------------------------------


@handle(ProjectServiceException, logger, message="Failed to list scenes.")
def get_scenes() -> list[IdDesc]:
    return rest.call(rest.Method.GET, f"{URL}/scenes", list_return_type=IdDesc)


@handle(ProjectServiceException, logger, message="Failed to get the scene.")
def get_scene(scene_id: str) -> Scene:
    return rest.call(rest.Method.GET, f"{URL}/scenes/{scene_id}", return_type=Scene)


@handle(ProjectServiceException, logger, message="Failed to add or update the scene.")
def update_scene(scene: Scene) -> datetime:

    assert scene.id
    return parse(rest.call(rest.Method.PUT, f"{URL}/scenes", return_type=str, body=scene))


@handle(ProjectServiceException, logger, message="Failed to delete the scene.")
def delete_scene(scene_id: str) -> None:
    rest.call(rest.Method.DELETE, f"{URL}/scenes/{scene_id}")
