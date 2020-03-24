import functools

from arcor2.server.globals import SCENE, PROJECT


def scene_needed(coro):
    @functools.wraps(coro)
    async def async_wrapper(*args, **kwargs):

        if SCENE is None or not SCENE.id:
            return False, "Scene not opened or has invalid id."
        return await coro(*args, **kwargs)

    return async_wrapper


def no_project(coro):
    @functools.wraps(coro)
    async def async_wrapper(*args, **kwargs):
        if PROJECT:
            return False, "Not available during project editing."
        return await coro(*args, **kwargs)

    return async_wrapper


def project_needed(coro):
    @functools.wraps(coro)
    async def async_wrapper(*args, **kwargs):

        if PROJECT is None or not PROJECT.id:
            return False, "Project not opened or has invalid id."
        return await coro(*args, **kwargs)

    return async_wrapper
