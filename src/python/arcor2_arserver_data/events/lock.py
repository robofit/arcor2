from dataclasses import dataclass

from dataclasses_jsonschema import JsonSchemaMixin

from arcor2.data.events import Event


@dataclass
class LockData(JsonSchemaMixin):

    object_ids: list[str]
    owner: str


@dataclass
class ObjectsLocked(Event):

    data: LockData


@dataclass
class ObjectsUnlocked(Event):

    data: LockData
