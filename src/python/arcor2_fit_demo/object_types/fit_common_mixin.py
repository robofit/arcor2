from dataclasses import dataclass
from typing import TYPE_CHECKING

from arcor2 import rest
from arcor2.object_types.abstract import Settings


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
