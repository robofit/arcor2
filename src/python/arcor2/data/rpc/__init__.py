import fastuuid as uuid

from arcor2.data.rpc import common


def get_id() -> int:
    """Generates unique ID suitable for RPC/orjson."""

    return uuid.uuid4().int % 2**32


__all__ = [
    common.__name__,
]
