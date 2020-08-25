from dataclasses import dataclass
from typing import Set, cast

from arcor2 import rest
from arcor2.object_types.abstract import Generic, Settings


@dataclass
class KinaliSettings(Settings):
    url: str
    configuration_id: str


class KinaliAbstractObject(Generic):
    """Object (without pose) that serves as a base class for standard feature
    services."""

    def __init__(self, obj_id: str, name: str, settings: KinaliSettings) -> None:
        super(KinaliAbstractObject, self).__init__(obj_id, name, settings)
        self._create()

    @property
    def settings(self) -> KinaliSettings:
        return cast(KinaliSettings, super(KinaliAbstractObject, self).settings)

    def cleanup(self) -> None:
        rest.put(f"{self.settings.url}/systems/destroy")

    def _active_configuration(self) -> str:
        return rest.get_primitive(f"{self.settings.url}/systems/active", str)

    def _get_configuration_ids(self) -> Set[str]:
        return set(rest.get_data(f"{self.settings.url}/systems"))

    def _create(self):
        if self._active_configuration() != self.settings.configuration_id:
            rest.put(f"{self.settings.url}/systems/{self.settings.configuration_id}/create")


__all__ = [
    KinaliSettings.__name__,
    KinaliAbstractObject.__name__,
]
