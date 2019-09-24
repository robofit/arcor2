# -*- coding: utf-8 -*-

from typing import List, Optional

from arcor2.data.common import ActionState, ProjectState, CurrentAction
from dataclasses import dataclass, field
from dataclasses_jsonschema import JsonSchemaMixin

from arcor2.data.common import Scene, Project

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
class CurrentActionEvent(Event):

    data: CurrentAction = field(default_factory=CurrentAction)
    event: str = field(default="currentAction", init=False)


# ----------------------------------------------------------------------------------------------------------------------


@dataclass
class ProjectStateEvent(Event):

    data: ProjectState = field(default_factory=ProjectState)
    event: str = field(default="projectState", init=False)

# ----------------------------------------------------------------------------------------------------------------------


@dataclass
class ActionStateEvent(Event):

    data: ActionState = field(default_factory=ActionState)
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
