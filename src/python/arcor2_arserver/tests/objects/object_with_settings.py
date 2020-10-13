from typing import cast

from arcor2.object_types.abstract import Generic
from arcor2.object_types.abstract import Settings as SettingsBase


class Settings(SettingsBase):

    str_param: str
    float_param: float
    bool_param: bool
    int_param: int


class ObjectWithSettings(Generic):
    """Object with some random settings."""

    _ABSTRACT = False

    def __init__(self, obj_id: str, name: str, settings: Settings) -> None:
        super(ObjectWithSettings, self).__init__(obj_id, name, settings)

    @property
    def settings(self) -> Settings:
        return cast(Settings, super(ObjectWithSettings, self).settings)
