from dataclasses import dataclass

from arcor2.data.common import Parameter
from arcor2.data.events import Event
from arcor2_arserver_data.objects import ObjectTypeMeta


@dataclass
class ChangedObjectTypes(Event):

    data: list[ObjectTypeMeta]


@dataclass
class OverrideUpdated(Event):
    data: Parameter
