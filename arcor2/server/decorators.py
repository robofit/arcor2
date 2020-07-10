import functools
from typing import Any, Callable, Coroutine, TypeVar, cast


from arcor2.exceptions import Arcor2Exception
from arcor2.server import globals as glob


F = TypeVar('F', bound=Callable[..., Coroutine[Any, Any, Any]])


def no_scene(coro: F) -> F:
    @functools.wraps(coro)
    async def async_wrapper(*args, **kwargs) -> Any:

        if glob.SCENE:
            raise Arcor2Exception("Scene has to be closed first.")
        return await coro(*args, **kwargs)

    return cast(F, async_wrapper)


def scene_needed(coro: F) -> F:
    @functools.wraps(coro)
    async def async_wrapper(*args, **kwargs) -> Any:

        if glob.SCENE is None or not glob.SCENE.id:
            raise Arcor2Exception("Scene not opened or has invalid id.")
        return await coro(*args, **kwargs)

    return cast(F, async_wrapper)


def no_project(coro: F) -> F:
    @functools.wraps(coro)
    async def async_wrapper(*args, **kwargs) -> Any:
        if glob.PROJECT:
            raise Arcor2Exception("Not available during project editing.")
        return await coro(*args, **kwargs)

    return cast(F, async_wrapper)


def project_needed(coro: F) -> F:
    @functools.wraps(coro)
    async def async_wrapper(*args, **kwargs) -> Any:

        if glob.PROJECT is None or not glob.PROJECT.id:
            raise Arcor2Exception("Project not opened or has invalid id.")
        return await coro(*args, **kwargs)

    return cast(F, async_wrapper)
