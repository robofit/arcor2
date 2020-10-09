import functools
from typing import Any, Callable, Optional, Type, TypeVar, cast

from arcor2.exceptions import Arcor2Exception

F = TypeVar("F", bound=Callable[..., Any])


def handle(
    raise_type: Type[Arcor2Exception],
    except_type: Type[Arcor2Exception] = Arcor2Exception,
    message: Optional[str] = None,
) -> Callable[[F], F]:
    def _handle_exceptions(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:

            try:
                return func(*args, **kwargs)
            except except_type as e:
                if message is not None:
                    raise raise_type(message) from e
                else:
                    raise raise_type(str(e)) from e

        return cast(F, wrapper)

    return _handle_exceptions
