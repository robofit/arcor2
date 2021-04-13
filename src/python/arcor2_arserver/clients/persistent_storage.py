from copy import deepcopy
from datetime import datetime
from typing import TYPE_CHECKING, Dict, Optional

from lru import LRU

from arcor2 import env
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

Caching can be disabled by setting respective environment variable - this is useful for environments
where ARServer is not the only one who touches Project service.
"""

_cache_enabled = env.get_bool("ARCOR2_ARSERVER_CACHE_ENABLED", True)
_cache_scenes = env.get_int("ARCOR2_ARSERVER_CACHE_SCENES", 16)
_cache_projects = env.get_int("ARCOR2_ARSERVER_CACHE_PROJECTS", 32)

if _cache_enabled:
    _cache_scenes = max(_cache_scenes, 1)
    _cache_projects = max(_cache_projects, 1)

# here we need to know all the items
_scenes_list: Optional[Dict[str, IdDesc]] = None
_projects_list: Optional[Dict[str, IdDesc]] = None

# here we can forget least used items
if TYPE_CHECKING:
    _scenes: Optional[Dict[str, Scene]] = None
    _projects: Optional[Dict[str, Project]] = None

    if _cache_enabled:
        _scenes = {}
        _projects = {}
else:
    _scenes = LRU(_cache_scenes) if _cache_enabled and _cache_scenes else None
    _projects = LRU(_cache_projects) if _cache_enabled and _cache_projects else None


async def initialize_module() -> None:

    if _cache_enabled:

        global _scenes_list
        global _projects_list

        _scenes_list = {}
        _projects_list = {}

        for it in (await ps.get_projects()).items:
            _projects_list[it.id] = it

        for it in (await ps.get_scenes()).items:
            _scenes_list[it.id] = it

        assert _scenes is not None
        assert _projects is not None

        _scenes.clear()
        _projects.clear()


async def get_projects() -> IdDescList:

    if _projects_list is not None:
        return IdDescList(items=list(_projects_list.values()))
    else:
        return await ps.get_projects()


async def get_scenes() -> IdDescList:

    if _scenes_list is not None:
        return IdDescList(items=list(_scenes_list.values()))
    else:
        return await ps.get_scenes()


async def get_project(project_id: str) -> Project:

    if not _cache_enabled:
        return await ps.get_project(project_id)

    assert _projects is not None

    if project_id not in _projects:
        _projects[project_id] = await ps.get_project(project_id)

    return _projects[project_id]


async def get_scene(scene_id: str) -> Scene:

    if not _cache_enabled:
        return await ps.get_scene(scene_id)

    assert _scenes is not None

    if scene_id not in _scenes:
        _scenes[scene_id] = await ps.get_scene(scene_id)

    return _scenes[scene_id]


async def update_project(project: Project) -> datetime:

    assert project.id
    ret = await ps.update_project(project)
    if _cache_enabled:
        assert _projects is not None
        assert _projects_list is not None
        _projects_list[project.id] = IdDesc(project.id, project.name, project.desc)
        _projects[project.id] = deepcopy(project)
        _projects[project.id].modified = ret
        _projects[project.id].int_modified = None
    return ret


async def update_scene(scene: Scene) -> datetime:

    assert scene.id
    ret = await ps.update_scene(scene)
    if _cache_enabled:
        assert _scenes is not None
        assert _scenes_list is not None
        _scenes_list[scene.id] = IdDesc(scene.id, scene.name, scene.desc)
        _scenes[scene.id] = deepcopy(scene)
        _scenes[scene.id].modified = ret
        _scenes[scene.id].int_modified = None

    return ret


async def delete_scene(scene_id: str) -> None:

    await ps.delete_scene(scene_id)
    if _cache_enabled:
        assert _scenes is not None
        assert _scenes_list is not None
        del _scenes_list[scene_id]
        del _scenes[scene_id]


async def delete_project(project_id: str) -> None:

    await ps.delete_project(project_id)
    if _cache_enabled:
        assert _projects is not None
        assert _projects_list is not None
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
