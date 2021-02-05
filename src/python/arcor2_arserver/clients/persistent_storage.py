from copy import deepcopy
from datetime import datetime
from typing import TYPE_CHECKING, Dict

from lru import LRU

from arcor2.clients import aio_persistent_storage as ps
from arcor2.clients.aio_persistent_storage import (
    delete_model,
    delete_object_type,
    get_mesh,
    get_meshes,
    get_model,
    get_object_type,
    get_object_type_ids,
    get_project_sources,
    put_model,
    update_object_type,
    update_project_sources,
)
from arcor2.clients.persistent_storage import ProjectServiceException
from arcor2.data.common import IdDesc, IdDescList, Project, Scene

"""
This module adds some caching capabilities to the aio version of persistent_storage. It should be only used by ARServer.
"""


# here we need to know all the items
_scenes_list: Dict[str, IdDesc] = {}
_projects_list: Dict[str, IdDesc] = {}

# here we can forget least used items
if TYPE_CHECKING:
    _scenes: Dict[str, Scene] = {}
    _projects: Dict[str, Project] = {}
else:
    _scenes = LRU(16)
    _projects = LRU(32)


async def initialize_module() -> None:

    _scenes.clear()
    _projects.clear()

    for it in (await ps.get_projects()).items:
        _projects_list[it.id] = it

    for it in (await ps.get_scenes()).items:
        _scenes_list[it.id] = it


async def get_projects() -> IdDescList:
    return IdDescList(items=list(_projects_list.values()))


async def get_scenes() -> IdDescList:
    return IdDescList(items=list(_scenes_list.values()))


async def get_project(project_id: str) -> Project:

    if project_id not in _projects:
        _projects[project_id] = await ps.get_project(project_id)

    return _projects[project_id]


async def get_scene(scene_id: str) -> Scene:

    if scene_id not in _scenes:
        _scenes[scene_id] = await ps.get_scene(scene_id)

    return _scenes[scene_id]


async def update_project(project: Project) -> datetime:

    assert project.id
    ret = await ps.update_project(project)
    _projects_list[project.id] = IdDesc(project.id, project.name, project.desc)
    _projects[project.id] = deepcopy(project)
    _projects[project.id].modified = ret
    _projects[project.id].int_modified = None
    return ret


async def update_scene(scene: Scene) -> datetime:

    assert scene.id
    ret = await ps.update_scene(scene)
    _scenes_list[scene.id] = IdDesc(scene.id, scene.name, scene.desc)
    _scenes[scene.id] = deepcopy(scene)
    _scenes[scene.id].modified = ret
    _scenes[scene.id].int_modified = None

    return ret


async def delete_scene(scene_id: str) -> None:

    await ps.delete_scene(scene_id)
    del _scenes_list[scene_id]
    del _scenes[scene_id]


async def delete_project(project_id: str) -> None:

    await ps.delete_project(project_id)
    del _projects_list[project_id]
    del _projects[project_id]


__all__ = [
    initialize_module.__name__,
    get_mesh.__name__,
    get_meshes.__name__,
    get_model.__name__,
    put_model.__name__,
    delete_model.__name__,
    get_projects.__name__,
    get_scenes.__name__,
    get_project.__name__,
    get_project_sources.__name__,
    get_scene.__name__,
    get_object_type.__name__,
    get_object_type_ids.__name__,
    update_project.__name__,
    update_scene.__name__,
    update_project_sources.__name__,
    update_object_type.__name__,
    delete_object_type.__name__,
    delete_scene.__name__,
    delete_project.__name__,
    ProjectServiceException.__name__,
]
