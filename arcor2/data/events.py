# -*- coding: utf-8 -*-

import re
from dataclasses import dataclass, field
from typing import List, Optional

from dataclasses_jsonschema import JsonSchemaMixin

from arcor2.data.common import ActionState, ProjectState, CurrentAction
from arcor2.data.common import Scene, Project


def wo_suffix(name: str) -> str:
    return re.sub('Event$', '', name)


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
    event: str = field(default=wo_suffix(__qualname__), init=False)  # type: ignore  # noqa: F821


@dataclass
class ProjectChangedEvent(Event):

    data: Optional[Project] = None
    event: str = field(default=wo_suffix(__qualname__), init=False)  # type: ignore  # noqa: F821


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
    event: str = field(default=wo_suffix(__qualname__), init=False)  # type: ignore  # noqa: F821


# ----------------------------------------------------------------------------------------------------------------------


@dataclass
class CurrentActionEvent(Event):

    data: CurrentAction = field(default_factory=CurrentAction)
    event: str = field(default=wo_suffix(__qualname__), init=False)  # type: ignore  # noqa: F821


# ----------------------------------------------------------------------------------------------------------------------


@dataclass
class ProjectStateEvent(Event):

    data: ProjectState = field(default_factory=ProjectState)
    event: str = field(default=wo_suffix(__qualname__), init=False)  # type: ignore  # noqa: F821

# ----------------------------------------------------------------------------------------------------------------------


@dataclass
class ActionStateEvent(Event):

    data: ActionState = field(default_factory=ActionState)
    event: str = field(default=wo_suffix(__qualname__), init=False)  # type: ignore  # noqa: F821


@dataclass
class ActionResult(JsonSchemaMixin):

    action_id: str = ""
    result: Optional[str] = field(default=None, metadata=dict(description="JSON-encoded result of the action."))
    error: Optional[str] = None


@dataclass
class ActionResultEvent(Event):

    data: ActionResult = field(default_factory=ActionResult)
    event: str = field(default=wo_suffix(__qualname__), init=False)  # type: ignore  # noqa: F821


"""
------------------------------------------------------------------------------------------------------------------------
Objects
------------------------------------------------------------------------------------------------------------------------
"""


@dataclass
class ObjectTypesChangedEvent(Event):

    data: List[str] = field(default_factory=list)  # changed object types
    event: str = field(default=wo_suffix(__qualname__), init=False)  # type: ignore  # noqa: F821
