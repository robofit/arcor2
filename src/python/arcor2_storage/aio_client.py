import functools
from typing import Any, Awaitable, Callable, TypeVar

from arcor2.helpers import run_in_executor
from arcor2_storage import client

StorageClientException = client.StorageClientException

F = TypeVar("F", bound=Callable[..., Any])


def _wrap(func: F) -> Callable[..., Awaitable[Any]]:
    @functools.wraps(func)
    async def inner(*args: Any, **kwargs: Any) -> Any:
        return await run_in_executor(func, *args, **kwargs)

    return inner


asset_info = _wrap(client.asset_info)
asset_ids = _wrap(client.asset_ids)
create_asset = _wrap(client.create_asset)
delete_asset = _wrap(client.delete_asset)
asset_exists = _wrap(client.asset_exists)
get_asset_data = _wrap(client.get_asset_data)

get_models = _wrap(client.get_models)
get_mesh = _wrap(client.get_mesh)
get_meshes = _wrap(client.get_meshes)
get_model = _wrap(client.get_model)
put_model = _wrap(client.put_model)
delete_model = _wrap(client.delete_model)

get_object_parameters = _wrap(client.get_object_parameters)
update_object_parameters = _wrap(client.update_object_parameters)

get_object_type = _wrap(client.get_object_type)
get_object_type_ids = _wrap(client.get_object_type_ids)
update_object_type = _wrap(client.update_object_type)
delete_object_type = _wrap(client.delete_object_type)

get_project_parameters = _wrap(client.get_project_parameters)
update_project_parameters = _wrap(client.update_project_parameters)

get_projects = _wrap(client.get_projects)
get_project = _wrap(client.get_project)
get_project_sources = _wrap(client.get_project_sources)
update_project = _wrap(client.update_project)
update_project_sources = _wrap(client.update_project_sources)
delete_project = _wrap(client.delete_project)
clone_project = _wrap(client.clone_project)

get_scenes = _wrap(client.get_scenes)
get_scene = _wrap(client.get_scene)
update_scene = _wrap(client.update_scene)
delete_scene = _wrap(client.delete_scene)
