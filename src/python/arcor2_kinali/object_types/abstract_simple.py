from dataclasses import dataclass
from typing import cast

from arcor2.object_types.abstract import Generic
from arcor2.object_types.abstract import Settings as BaseSettings


@dataclass
class Settings(BaseSettings):
    url: str


class AbstractSimple(Generic):
    """Object (without pose) that serves as a base class for feature services
    without 'Configurations' and 'System' controllers."""

    def __init__(self, obj_id: str, name: str, settings: Settings) -> None:
        super(AbstractSimple, self).__init__(obj_id, name, settings)

    @property
    def settings(self) -> Settings:
        return cast(Settings, super(AbstractSimple, self).settings)


__all__ = [
    Settings.__name__,
    AbstractSimple.__name__,
]
