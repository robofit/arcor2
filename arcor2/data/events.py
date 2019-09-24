# -*- coding: utf-8 -*-

from typing import List, Optional
from enum import Enum

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

    event: str = field(default="", init=False)


"""
------------------------------------------------------------------------------------------------------------------------
Project / scene
------------------------------------------------------------------------------------------------------------------------
"""


@dataclass
class SceneChangedEvent(Event):

    data: Optional[Scene] = None
    event: str = field(default="sceneChanged", init=False)


@dataclass
class ProjectChangedEvent(Event):

    data: Optional[Project] = None
    event: str = field(default="projectChanged", init=False)


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
    event: str = field(default="projectException", init=False)


# ----------------------------------------------------------------------------------------------------------------------


@dataclass
class CurrentActionEventData(JsonSchemaMixin):

    action_id: str = ""
    args: List[ActionParameter] = field(default_factory=list)


@dataclass
class CurrentActionEvent(Event):

    data: CurrentActionEventData = field(default_factory=CurrentActionEventData)
    event: str = field(default="currentAction", init=False)


# ----------------------------------------------------------------------------------------------------------------------


class ProjectStateEnum(Enum):

    RUNNING: str = "running"
    STOPPED: str = "stopped"
    PAUSED: str = "paused"
    RESUMED: str = "resumed"


@dataclass
class ProjectStateEventData(JsonSchemaMixin):

    state: ProjectStateEnum = ProjectStateEnum.STOPPED


@dataclass
class ProjectStateEvent(Event):

    data: ProjectStateEventData = field(default_factory=ProjectStateEventData)
    event: str = field(default="projectState", init=False)

# ----------------------------------------------------------------------------------------------------------------------


class ActionStateEnum(Enum):

    BEFORE: str = "before"
    AFTER: str = "after"


@dataclass
class ActionStateEventData(JsonSchemaMixin):

    object_id: str = ""
    method: str = ""
    where: ActionStateEnum = ActionStateEnum.BEFORE


@dataclass
class ActionStateEvent(Event):

    data: ActionStateEventData = field(default_factory=ActionStateEventData)
    event: str = field(default="actionState", init=False)


"""
------------------------------------------------------------------------------------------------------------------------
Objects
------------------------------------------------------------------------------------------------------------------------
"""


@dataclass
class ObjectTypesChangedEvent(Event):

    data: List[str] = field(default_factory=list)  # changed object types
    event: str = field(default="objectTypesChanged", init=False)
