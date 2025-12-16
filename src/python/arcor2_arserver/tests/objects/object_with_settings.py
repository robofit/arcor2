from dataclasses import dataclass

from arcor2.exceptions import Arcor2Exception
from arcor2_object_types.abstract import Generic
from arcor2_object_types.abstract import Settings as SettingsBase


@dataclass
class Settings(SettingsBase):
    str_param: str
    float_param: float
    bool_param: bool
    int_param: int
    str_param_default: str = "default"


class ObjectWithSettings(Generic):
    """Object with some random settings."""

    INT_PARAM_SPECIAL_VALUE: int = 100

    _ABSTRACT = False

    def __init__(self, obj_id: str, name: str, settings: Settings) -> None:
        super(ObjectWithSettings, self).__init__(obj_id, name, settings)
        assert isinstance(settings, Settings)

        # this is intended to test overrides
        if settings.int_param != self.INT_PARAM_SPECIAL_VALUE:
            raise Arcor2Exception(f"int_param ({settings.int_param}) has to be set to {self.INT_PARAM_SPECIAL_VALUE}.")

    @property
    def settings(self) -> Settings:
        assert isinstance(self._settings, Settings)
        return self._settings
