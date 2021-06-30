from dataclasses import dataclass
from typing import List

from dataclasses_jsonschema import JsonSchemaMixin

from arcor2.data.events import Event


@dataclass
class LockData(JsonSchemaMixin):

    object_ids: List[str]
    owner: str


@dataclass
class ObjectsLocked(Event):

    data: LockData


@dataclass
class ObjectsUnlocked(Event):

    data: LockData
