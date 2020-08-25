from dataclasses import dataclass, field
from typing import List

from arcor2.data.events import Event, wo_suffix
from arcor2_arserver_data.objects import ObjectTypeMeta


@dataclass
class ChangedObjectTypesEvent(Event):

    data: List[ObjectTypeMeta] = field(default_factory=list)  # changed object types
    event: str = field(default=wo_suffix(__qualname__), init=False)  # type: ignore  # noqa: F821
