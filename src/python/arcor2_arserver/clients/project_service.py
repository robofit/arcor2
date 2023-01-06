import asyncio
import time
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, Any, Awaitable, Callable

from lru import LRU

from arcor2 import env
from arcor2.cached import CachedProject, CachedScene
from arcor2.clients import aio_project_service as ps
from arcor2.clients.aio_project_service import (
    delete_model,
    get_mesh,
    get_meshes,
    get_model,
    get_project_sources,
    put_model,
    update_project_sources,
)
from arcor2.clients.project_service import ProjectServiceException
from arcor2.data.common import IdDesc
from arcor2.data.object_type import ObjectType
from arcor2.exceptions import Arcor2Exception


@dataclass
class CachedListing:

    __slots__ = "listing", "ts"

    listing: dict[str, IdDesc]
    ts: float

    def time_to_update(self) -> bool:
        return time.monotonic() - self.ts > _cache_timeout


"""
This module adds some caching capabilities to the aio version of project_service. It should be only used by ARServer.

Caching can be disabled by setting respective environment variable - this is useful for environments
where ARServer is not the only one who touches Project service.
"""

_cache_timeout = max(env.get_float("ARCOR2_ARSERVER_CACHE_TIMEOUT", 1.0), 0)
_cache_scenes = max(env.get_int("ARCOR2_ARSERVER_CACHE_SCENES", 32), 1)
_cache_projects = max(env.get_int("ARCOR2_ARSERVER_CACHE_PROJECTS", 64), 1)
_cache_object_types = max(env.get_int("ARCOR2_ARSERVER_CACHE_OBJECT_TYPES", 64), 1)

# here we need to know all the items
_scenes_list = CachedListing({}, 0)
_projects_list = CachedListing({}, 0)
_object_type_list = CachedListing({}, 0)

_scenes_list_lock = asyncio.Lock()
_projects_list_lock = asyncio.Lock()
_object_type_lock = asyncio.Lock()

# here we can forget the least used items
if TYPE_CHECKING:
    _scenes: dict[str, CachedScene] = {}
    _projects: dict[str, CachedProject] = {}
    _object_types: dict[str, ObjectType] = {}
else:
    _scenes = LRU(_cache_scenes)
    _projects = LRU(_cache_projects)
    _object_types = LRU(_cache_object_types)


async def _update_list(
    getter: Callable[..., Awaitable[list[IdDesc]]], cached_listing: CachedListing, cache: dict[str, Any]
) -> None:

    if not cached_listing.time_to_update():
        return

    updated = {it.id: it for it in (await getter())}
    for deleted in cached_listing.listing.keys() - updated.keys():  # remove outdated items from the cache
        cache.pop(deleted, None)
    cached_listing.listing = updated
    cached_listing.ts = time.monotonic()


async def initialize_module() -> None:

    await asyncio.gather(
        _update_list(ps.get_projects, _projects_list, _projects),
        _update_list(ps.get_scenes, _scenes_list, _scenes),
        _update_list(ps.get_object_type_ids, _object_type_list, _object_types),
    )

    _scenes.clear()
    _projects.clear()
    _object_types.clear()


async def get_project_ids() -> set[str]:

    async with _projects_list_lock:
        await _update_list(ps.get_projects, _projects_list, _projects)
    return set(_projects_list.listing)


async def get_projects() -> list[IdDesc]:

    async with _projects_list_lock:
        await _update_list(ps.get_projects, _projects_list, _projects)
    return list(_projects_list.listing.values())


async def get_scene_ids() -> set[str]:

    async with _scenes_list_lock:
        await _update_list(ps.get_scenes, _scenes_list, _scenes)
    return set(_scenes_list.listing)


async def get_scenes() -> list[IdDesc]:

    async with _scenes_list_lock:
        await _update_list(ps.get_scenes, _scenes_list, _scenes)
    return list(_scenes_list.listing.values())


async def get_object_type_ids() -> set[str]:

    async with _object_type_lock:
        await _update_list(ps.get_object_type_ids, _object_type_list, _object_types)
    return set(_object_type_list.listing)


async def get_object_types() -> list[IdDesc]:

    async with _object_type_lock:
        await _update_list(ps.get_object_type_ids, _object_type_list, _object_types)
    return list(_object_type_list.listing.values())


async def get_object_type_iddesc(object_type_id: str) -> IdDesc:

    async with _object_type_lock:
        await _update_list(ps.get_object_type_ids, _object_type_list, _object_types)
    try:
        return _object_type_list.listing[object_type_id]
    except KeyError:
        raise ProjectServiceException("Unknown object type.")


async def get_project(project_id: str) -> CachedProject:

    async with _projects_list_lock:
        try:
            project = _projects[project_id]
            assert project.modified
        except KeyError:
            project = CachedProject(await ps.get_project(project_id))
            _projects[project_id] = project
        else:
            await _update_list(ps.get_projects, _projects_list, _projects)

            if project_id not in _projects_list.listing:
                _projects.pop(project_id, None)
                raise Arcor2Exception("Project removed externally.")

            # project in cache is outdated
            if project.modified < _projects_list.listing[project_id].modified:
                project = CachedProject(await ps.get_project(project_id))
                _projects[project_id] = project

    return project


async def get_scene(scene_id: str) -> CachedScene:

    async with _scenes_list_lock:
        try:
            scene = _scenes[scene_id]
            assert scene.modified
        except KeyError:
            scene = CachedScene(await ps.get_scene(scene_id))
            _scenes[scene_id] = scene
        else:
            await _update_list(ps.get_scenes, _scenes_list, _scenes)

            if scene_id not in _scenes_list.listing:
                _scenes.pop(scene_id, None)
                raise Arcor2Exception("Scene removed externally.")

            # scene in cache is outdated
            if scene.modified < _scenes_list.listing[scene_id].modified:
                scene = CachedScene(await ps.get_scene(scene_id))
                _scenes[scene_id] = scene

    return scene


async def get_object_type(object_type_id: str) -> ObjectType:

    async with _object_type_lock:
        try:
            ot = _object_types[object_type_id]
            assert ot.modified
        except KeyError:
            ot = await ps.get_object_type(object_type_id)
            _object_types[object_type_id] = ot
        else:
            await _update_list(ps.get_object_type_ids, _object_type_list, _object_types)

            if object_type_id not in _object_type_list.listing:
                _object_types.pop(object_type_id, None)
                raise Arcor2Exception("ObjectType removed externally.")

            # ObjectType in cache is outdated
            if ot.modified < _object_type_list.listing[object_type_id].modified:
                ot = await ps.get_object_type(object_type_id)
                _object_types[object_type_id] = ot

    return ot


async def update_project(project: CachedProject) -> datetime:

    assert project.id

    ret = await ps.update_project(project.project)
    project.modified = ret

    if not project.created:
        project.created = project.modified

    _projects_list.listing[project.id] = IdDesc(
        project.id, project.name, project.created, project.modified, project.description
    )
    _projects[project.id] = deepcopy(project)
    _projects[project.id].int_modified = None

    return ret


async def update_scene(scene: CachedScene) -> datetime:

    assert scene.id

    ret = await ps.update_scene(scene.scene)
    scene.modified = ret

    if not scene.created:
        scene.created = scene.modified

    _scenes_list.listing[scene.id] = IdDesc(scene.id, scene.name, scene.created, scene.modified, scene.description)
    _scenes[scene.id] = deepcopy(scene)
    _scenes[scene.id].int_modified = None

    return ret


async def update_object_type(object_type: ObjectType) -> datetime:

    assert object_type.id

    ret = await ps.update_object_type(object_type)
    object_type.modified = ret

    if not object_type.created:
        object_type.created = object_type.modified

    _object_type_list.listing[object_type.id] = IdDesc(
        object_type.id, "", object_type.created, object_type.modified, object_type.description
    )
    _object_types[object_type.id] = deepcopy(object_type)

    return ret


async def delete_scene(scene_id: str) -> None:

    await ps.delete_scene(scene_id)
    _scenes_list.listing.pop(scene_id, None)
    _scenes.pop(scene_id, None)


async def delete_project(project_id: str) -> None:

    await ps.delete_project(project_id)
    _projects_list.listing.pop(project_id, None)
    _projects.pop(project_id, None)


async def delete_object_type(object_type_id: str) -> None:

    await ps.delete_object_type(object_type_id)
    _object_type_list.listing.pop(object_type_id, None)
    _object_types.pop(object_type_id, None)


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
    get_object_types.__name__,
    update_project.__name__,
    update_scene.__name__,
    update_project_sources.__name__,
    update_object_type.__name__,
    delete_object_type.__name__,
    delete_scene.__name__,
    delete_project.__name__,
    ProjectServiceException.__name__,
    get_scene_ids.__name__,
    get_project_ids.__name__,
    get_object_type_ids.__name__,
]
