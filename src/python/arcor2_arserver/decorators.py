import functools
from asyncio import sleep
from typing import Any, Callable, Coroutine, Type, TypeVar, cast

from arcor2.exceptions import Arcor2Exception
from arcor2_arserver import globals as glob
from arcor2_arserver.lock.exceptions import LockingException

F = TypeVar("F", bound=Callable[..., Coroutine[Any, Any, Any]])


def no_scene(coro: F) -> F:
    @functools.wraps(coro)
    async def async_wrapper(*args, **kwargs) -> Any:

        if glob.LOCK.scene:
            raise Arcor2Exception("Scene has to be closed first.")
        return await coro(*args, **kwargs)

    return cast(F, async_wrapper)


def scene_needed(coro: F) -> F:
    @functools.wraps(coro)
    async def async_wrapper(*args, **kwargs) -> Any:

        if glob.LOCK.scene is None or not glob.LOCK.scene.id:
            raise Arcor2Exception("Scene not opened or has invalid id.")
        return await coro(*args, **kwargs)

    return cast(F, async_wrapper)


def no_project(coro: F) -> F:
    @functools.wraps(coro)
    async def async_wrapper(*args, **kwargs) -> Any:
        if glob.LOCK.project:
            raise Arcor2Exception("Not available during project editing.")
        return await coro(*args, **kwargs)

    return cast(F, async_wrapper)


def project_needed(coro: F) -> F:
    @functools.wraps(coro)
    async def async_wrapper(*args, **kwargs) -> Any:

        if glob.LOCK.project is None or not glob.LOCK.project.id:
            raise Arcor2Exception("Project not opened or has invalid id.")
        return await coro(*args, **kwargs)

    return cast(F, async_wrapper)


def retry(exc: Type[Exception] = LockingException, tries: int = 1, delay: float = 0) -> Callable:
    """Retry decorator.

    :param exc: Exception or tuple of exceptions to catch
    :param tries: number of attempts
    :param delay: delay between attempts
    :return:
    """

    async def _retry_call(_tries: int, coro: F, *args, **kwargs) -> Any:
        """
        Internal part of retry decorator - handles exceptions, delay and tries
        """
        while _tries:
            try:
                return await coro(*args, **kwargs)
            except exc:
                _tries -= 1
                if _tries == 0:
                    raise

                if delay > 0:
                    await sleep(delay)

    def _retry(coro: F) -> F:
        @functools.wraps(coro)
        async def async_wrapper(*fargs, **fkwargs) -> Any:
            return await _retry_call(tries, coro, *fargs, **fkwargs)

        return cast(F, async_wrapper)

    return _retry
