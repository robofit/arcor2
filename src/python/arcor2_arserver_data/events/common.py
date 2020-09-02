from dataclasses import dataclass
from typing import Optional

from dataclasses_jsonschema import JsonSchemaMixin

from arcor2.data import common
from arcor2.data.events import Event


@dataclass
class ShowMainScreen(Event):
    @dataclass
    class Data(JsonSchemaMixin):
        class WhatEnum(common.StrEnum):
            ScenesList: str = "ScenesList"
            ProjectsList: str = "ProjectsList"
            PackagesList: str = "PackagesList"

        what: WhatEnum
        highlight: Optional[str] = None

    data: Data
