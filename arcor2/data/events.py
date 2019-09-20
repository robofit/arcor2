# -*- coding: utf-8 -*-

from typing import List, Optional, Dict, Type
from typing_extensions import Final
from enum import Enum
import inspect
import sys

from dataclasses import dataclass, field
from dataclasses_jsonschema import JsonSchemaMixin

from arcor2.data.common import Scene, Project, ActionParameter

"""
------------------------------------------------------------------------------------------------------------------------
Common stuff
------------------------------------------------------------------------------------------------------------------------
"""


@dataclass
class Event(JsonSchemaMixin):

    event: str = ""


@dataclass
class ObjectTypesUpdatedEvent(Event):
    event: Final[str] = "objectTypesUpdated"


"""
------------------------------------------------------------------------------------------------------------------------
Project / scene
------------------------------------------------------------------------------------------------------------------------
"""


@dataclass
class SceneChangedEvent(Event):

    data: Optional[Scene] = None
    event: Final[str] = "sceneChanged"


@dataclass
class ProjectChangedEvent(Event):

    data: Optional[Project] = None
    event: Final[str] = "projectChanged"


"""
------------------------------------------------------------------------------------------------------------------------
Project execution
------------------------------------------------------------------------------------------------------------------------
"""


@dataclass
class ProjectExceptionEventData(JsonSchemaMixin):

    message: str = field(default_factory=str)
    type: str = field(default_factory=str)
    handled: bool = False


@dataclass
class ProjectExceptionEvent(Event):

    data: ProjectExceptionEventData = field(default_factory=ProjectExceptionEventData)
    event: Final[str] = "projectException"


# ----------------------------------------------------------------------------------------------------------------------


@dataclass
class CurrentActionEventData(JsonSchemaMixin):

    action_id: str
    args: List[ActionParameter] = field(default_factory=list)


@dataclass
class CurrentActionEvent(Event):

    data: CurrentActionEventData = field(default_factory=CurrentActionEventData)
    event: Final[str] = "currentAction"


# ----------------------------------------------------------------------------------------------------------------------


class ProjectStateEnum(Enum):

    RUNNING: str = "running"
    STOPPED: str = "stopped"
    PAUSED: str = "paused"
    RESUMED: str = "resumed"


@dataclass
class ProjectStateEventData(JsonSchemaMixin):

    state: ProjectStateEnum


@dataclass
class ProjectStateEvent(Event):

    data: ProjectStateEventData = field(default_factory=ProjectStateEventData)
    event: Final[str] = "projectState"

# ----------------------------------------------------------------------------------------------------------------------


class ActionStateEnum(Enum):

    BEFORE: str = "before"
    AFTER: str = "after"


@dataclass
class ActionStateEventData(JsonSchemaMixin):

    method: str
    where: ActionStateEnum


@dataclass
class ActionStateEvent(Event):

    data: ActionStateEventData = field(default_factory=ActionStateEventData)
    event: Final[str] = "actionState"


EVENT_MAPPING: Dict[str, Type[Event]] = {}

for name, obj in inspect.getmembers(sys.modules[__name__]):
    if inspect.isclass(obj) and issubclass(obj, Event) and obj != Event:
        EVENT_MAPPING[obj.event] = obj
