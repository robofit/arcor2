import functools
import logging
from typing import Any, Callable, TypeVar, cast

from arcor2.exceptions import Arcor2Exception

F = TypeVar("F", bound=Callable[..., Any])


def handle(
    raise_type: type[Arcor2Exception],
    logger: logging.Logger,
    except_type: type[Arcor2Exception] = Arcor2Exception,
    message: None | str = None,
) -> Callable[[F], F]:
    def _handle_exceptions(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:

            try:
                return func(*args, **kwargs)
            except except_type as e:
                if message is not None:
                    logger.error(f"{message} {str(e)}")
                    raise raise_type(message) from e
                else:
                    logger.error(str(e))
                    raise raise_type(str(e)) from e

        return cast(F, wrapper)

    return _handle_exceptions
