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
        rest.put(f"{self.settings.url}/system/set", params={"configId": self.settings.configuration_id, "id": self.id})

    @property
    def settings(self) -> KinaliSettings:
        return cast(KinaliSettings, super(KinaliAbstractObject, self).settings)

    def configurations(self) -> Set[str]:
        return set(rest.get_list_primitive(f"{self.settings.url}/configurations", str))

    def cleanup(self) -> None:
        super(KinaliAbstractObject, self).cleanup()
        rest.put(f"{self.settings.url}/system/reset")


__all__ = [
    KinaliSettings.__name__,
    KinaliAbstractObject.__name__,
]
