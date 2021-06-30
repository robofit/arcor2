import json
from typing import Any, Dict, Sequence, Type, TypeVar, Union

from arcor2.exceptions import Arcor2Exception


class JsonException(Arcor2Exception):
    pass


JsonType = Union[bool, str, int, float, Dict[str, Any], Sequence[Any], None]


T = TypeVar("T")


def loads(value: str) -> JsonType:

    try:
        return json.loads(value)
    except (ValueError, TypeError) as e:
        raise JsonException(f"Not a JSON. {str(e)}") from e


def loads_type(value: str, output_type: Type[T]) -> T:

    val = loads(value)

    if not isinstance(val, output_type):
        raise JsonException("Not an expected type.")

    return val


def dumps(value: JsonType) -> str:

    try:
        return json.dumps(value)
    except (ValueError, TypeError) as e:
        raise JsonException(f"Not a JSON. {str(e)}") from e
