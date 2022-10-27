from typing import Any, Sequence, TypeVar

import orjson

from arcor2.exceptions import Arcor2Exception


class JsonException(Arcor2Exception):
    pass


JsonType = bool | str | int | float | dict[str, Any] | Sequence[Any] | None


T = TypeVar("T")


def loads(value: str) -> JsonType:

    try:
        return orjson.loads(value)
    except (ValueError, TypeError) as e:
        raise JsonException(f"Not a JSON. {str(e)}") from e


def loads_type(value: str, output_type: type[T]) -> T:

    val = loads(value)

    if not isinstance(val, output_type):
        raise JsonException("Not an expected type.")

    return val


def dumps(value: JsonType) -> str:

    try:
        return orjson.dumps(value).decode()
    except (ValueError, TypeError) as e:
        raise JsonException(f"Not a JSON. {str(e)}") from e
