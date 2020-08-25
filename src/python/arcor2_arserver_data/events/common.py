from dataclasses import dataclass, field
from typing import Optional

from dataclasses_jsonschema import JsonSchemaMixin

from arcor2.data import common
from arcor2.data.events import Event, wo_suffix


@dataclass
class ShowMainScreenData(JsonSchemaMixin):
    class WhatEnum(common.StrEnum):

        ScenesList: str = "ScenesList"
        ProjectsList: str = "ProjectsList"
        PackagesList: str = "PackagesList"

    what: WhatEnum
    highlight: Optional[str] = None


@dataclass
class ShowMainScreenEvent(Event):

    data: Optional[ShowMainScreenData] = None
    event: str = field(default=wo_suffix(__qualname__), init=False)  # type: ignore  # noqa: F821
