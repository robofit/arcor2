from dataclasses import dataclass
from typing import TYPE_CHECKING

from arcor2_object_types.abstract import Settings
from arcor2_web import rest


@dataclass
class UrlSettings(Settings):
    url: str = "http://"


class FitCommonMixin:
    if TYPE_CHECKING:
        settings = UrlSettings("")

    def _started(self) -> bool:
        return rest.call(rest.Method.GET, f"{self.settings.url}/state/started", return_type=bool)

    def _stop(self) -> None:
        rest.call(rest.Method.PUT, f"{self.settings.url}/state/stop")
