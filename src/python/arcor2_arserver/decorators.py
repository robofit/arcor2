import functools
from asyncio import sleep
from typing import Any, Callable, Coroutine, TypeVar, cast

from arcor2_arserver import logger
from arcor2_arserver.lock.exceptions import LockingException

F = TypeVar("F", bound=Callable[..., Coroutine[Any, Any, Any]])


def retry(exc: type[Exception] = LockingException, tries: int = 1, delay: float = 0) -> Callable:
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
                ret = await coro(*args, **kwargs)
                if _tries < tries * 0.75:
                    logger.warn(f"Retry timeout took {(tries - _tries) * delay}")
                return ret
            except exc:
                _tries -= 1
                if _tries == 0:
                    logger.warn("Retry raised")
                    raise

                if delay > 0:
                    await sleep(delay)

    def _retry(coro: F) -> F:
        @functools.wraps(coro)
        async def async_wrapper(*fargs, **fkwargs) -> Any:
            return await _retry_call(tries, coro, *fargs, **fkwargs)

        return cast(F, async_wrapper)

    return _retry
