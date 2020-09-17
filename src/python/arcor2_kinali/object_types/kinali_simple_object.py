from dataclasses import dataclass
from typing import cast

from arcor2.object_types.abstract import Generic, Settings


@dataclass
class KinaliSimpleSettings(Settings):
    url: str


class KinaliSimpleObject(Generic):
    """Object (without pose) that serves as a base class for standard feature
    services."""

    def __init__(self, obj_id: str, name: str, settings: KinaliSimpleSettings) -> None:
        super(KinaliSimpleObject, self).__init__(obj_id, name, settings)

    @property
    def settings(self) -> KinaliSimpleSettings:
        return cast(KinaliSimpleSettings, super(KinaliSimpleObject, self).settings)


__all__ = [
    KinaliSimpleSettings.__name__,
    KinaliSimpleObject.__name__,
]
