import asyncio
import time
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, Dict

from lru import LRU

from arcor2 import env
from arcor2.clients import aio_persistent_storage as ps
from arcor2.clients.aio_persistent_storage import (
    delete_model,
    get_mesh,
    get_meshes,
    get_model,
    get_project_sources,
    put_model,
    update_project_sources,
)
from arcor2.clients.persistent_storage import ProjectServiceException
from arcor2.data.common import IdDesc, IdDescList, Project, Scene
from arcor2.data.object_type import ObjectType
from arcor2.exceptions import Arcor2Exception


@dataclass
class CachedListing:

    listing: Dict[str, IdDesc]
    ts: float

    def time_to_update(self) -> bool:
        return time.monotonic() - self.ts > 1.0


"""
This module adds some caching capabilities to the aio version of persistent_storage. It should be only used by ARServer.

Caching can be disabled by setting respective environment variable - this is useful for environments
where ARServer is not the only one who touches Project service.
"""

_cache_scenes = max(env.get_int("ARCOR2_ARSERVER_CACHE_SCENES", 32), 1)
_cache_projects = max(env.get_int("ARCOR2_ARSERVER_CACHE_PROJECTS", 64), 1)
_cache_object_types = max(env.get_int("ARCOR2_ARSERVER_CACHE_OBJECT_TYPES", 64), 1)

# here we need to know all the items
_scenes_list = CachedListing({}, 0)
_projects_list = CachedListing({}, 0)
_object_type_list = CachedListing({}, 0)

# here we can forget least used items
if TYPE_CHECKING:
    _scenes: Dict[str, Scene] = {}
    _projects: Dict[str, Project] = {}
    _object_types: Dict[str, ObjectType] = {}
else:
    _scenes = LRU(_cache_scenes)
    _projects = LRU(_cache_projects)
    _object_types = LRU(_cache_object_types)


async def _update_projects_list() -> None:

    _projects_list.listing.clear()
    for it in (await ps.get_projects()).items:
        _projects_list.listing[it.id] = it
    _projects_list.ts = time.monotonic()


async def _update_scenes_list() -> None:

    _scenes_list.listing.clear()
    for it in (await ps.get_scenes()).items:
        _scenes_list.listing[it.id] = it
    _scenes_list.ts = time.monotonic()


async def _update_object_types_list() -> None:

    _object_type_list.listing.clear()
    for it in (await ps.get_object_type_ids()).items:
        _object_type_list.listing[it.id] = it
    _object_type_list.ts = time.monotonic()


async def initialize_module() -> None:

    await asyncio.gather(*[_update_projects_list(), _update_scenes_list(), _update_object_types_list()])

    _scenes.clear()
    _projects.clear()
    _object_types.clear()


async def get_projects() -> IdDescList:

    if not _projects_list or _projects_list.time_to_update():
        await _update_projects_list()

    return IdDescList(items=list(_projects_list.listing.values()))


async def get_scenes() -> IdDescList:

    if not _scenes_list or _scenes_list.time_to_update():
        await _update_scenes_list()

    return IdDescList(items=list(_scenes_list.listing.values()))


async def get_object_type_ids() -> IdDescList:

    if not _object_type_list or _object_type_list.time_to_update():
        await _update_object_types_list()

    return IdDescList(items=list(_object_type_list.listing.values()))


async def get_project(project_id: str) -> Project:

    try:
        project = _projects[project_id]
        assert project.modified
    except KeyError:
        project = await ps.get_project(project_id)
        _projects[project_id] = project
    else:
        if _projects_list.time_to_update():
            await _update_projects_list()

        if project_id not in _projects_list.listing:
            del _projects[project_id]
            raise Arcor2Exception("Project removed externally.")

        # project in cache is outdated
        if project.modified < _projects_list.listing[project_id].modified:
            project = await ps.get_project(project_id)
            _projects[project_id] = project

    return project


async def get_scene(scene_id: str) -> Scene:

    try:
        scene = _scenes[scene_id]
        assert scene.modified
    except KeyError:
        scene = await ps.get_scene(scene_id)
        _scenes[scene_id] = scene
    else:
        if not _scenes_list or _scenes_list.time_to_update():
            await _update_scenes_list()

        if scene_id not in _scenes_list.listing:
            del _scenes[scene_id]
            raise Arcor2Exception("Scene removed externally.")

        # scene in cache is outdated
        if scene.modified < _scenes_list.listing[scene_id].modified:
            scene = await ps.get_scene(scene_id)
            _scenes[scene_id] = scene

    return scene


async def get_object_type(object_type_id: str) -> ObjectType:

    try:
        ot = _object_types[object_type_id]
        assert ot.modified
    except KeyError:
        ot = await ps.get_object_type(object_type_id)
        _object_types[object_type_id] = ot
    else:
        if not _object_type_list or _object_type_list.time_to_update():
            await _update_object_types_list()

        if object_type_id not in _object_type_list.listing:
            del _object_types[object_type_id]
            raise Arcor2Exception("ObjectType removed externally.")

        # ObjectType in cache is outdated
        if ot.modified < _object_type_list.listing[object_type_id].modified:
            ot = await ps.get_object_type(object_type_id)
            _object_types[object_type_id] = ot

    return ot


async def update_project(project: Project) -> datetime:

    assert project.id
    assert _projects_list

    ret = await ps.update_project(project)
    project.modified = ret

    _projects_list.listing[project.id] = IdDesc(project.id, project.name, project.modified, project.desc)
    _projects[project.id] = deepcopy(project)
    _projects[project.id].int_modified = None

    return ret


async def update_scene(scene: Scene) -> datetime:

    assert scene.id
    assert _scenes_list

    ret = await ps.update_scene(scene)
    scene.modified = ret

    _scenes_list.listing[scene.id] = IdDesc(scene.id, scene.name, scene.modified, scene.desc)
    _scenes[scene.id] = deepcopy(scene)
    _scenes[scene.id].int_modified = None

    return ret


async def update_object_type(object_type: ObjectType) -> datetime:

    assert object_type.id
    assert _object_type_list

    ret = await ps.update_object_type(object_type)
    object_type.modified = ret

    _object_type_list.listing[object_type.id] = IdDesc(object_type.id, "", object_type.modified, object_type.desc)
    _object_types[object_type.id] = deepcopy(object_type)

    return ret


async def delete_scene(scene_id: str) -> None:

    await ps.delete_scene(scene_id)

    try:
        del _scenes_list.listing[scene_id]
        del _scenes[scene_id]
    except KeyError:
        pass


async def delete_project(project_id: str) -> None:

    await ps.delete_project(project_id)

    try:
        del _projects_list.listing[project_id]
        del _projects[project_id]
    except KeyError:
        pass


async def delete_object_type(object_type_id: str) -> None:

    await ps.delete_object_type(object_type_id)

    try:
        del _object_type_list.listing[object_type_id]
        del _object_types[object_type_id]
    except KeyError:
        pass


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
