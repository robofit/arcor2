import functools

from arcor2.server import globals as glob


def no_scene(coro):
    @functools.wraps(coro)
    async def async_wrapper(*args, **kwargs):

        if glob.SCENE:
            return False, "Scene has to be closed first."
        return await coro(*args, **kwargs)

    return async_wrapper


def scene_needed(coro):
    @functools.wraps(coro)
    async def async_wrapper(*args, **kwargs):

        if glob.SCENE is None or not glob.SCENE.id:
            return False, "Scene not opened or has invalid id."
        return await coro(*args, **kwargs)

    return async_wrapper


def no_project(coro):
    @functools.wraps(coro)
    async def async_wrapper(*args, **kwargs):
        if glob.PROJECT:
            return False, "Not available during project editing."
        return await coro(*args, **kwargs)

    return async_wrapper


def project_needed(coro):
    @functools.wraps(coro)
    async def async_wrapper(*args, **kwargs):

        if glob.PROJECT is None or not glob.PROJECT.id:
            return False, "Project not opened or has invalid id."
        return await coro(*args, **kwargs)

    return async_wrapper
