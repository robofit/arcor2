# -*- coding: utf-8 -*-

import re
from dataclasses import dataclass, field
from typing import Optional

from dataclasses_jsonschema import JsonSchemaMixin

from arcor2.data import common, execution


def wo_suffix(name: str) -> str:
    return re.sub("Event$", "", name)


class EventType(common.StrEnum):

    ADD: str = "add"
    UPDATE: str = "update"
    REMOVE: str = "remove"
    UPDATE_BASE: str = "update_base"


"""
------------------------------------------------------------------------------------------------------------------------
Common stuff
------------------------------------------------------------------------------------------------------------------------
"""


@dataclass
class Event(JsonSchemaMixin):

    event: str = field(default="", init=False)
    change_type: Optional[EventType] = None
    parent_id: Optional[str] = None


@dataclass
class NotificationEventData(JsonSchemaMixin):
    class NotificationLevel(common.StrEnum):
        INFO: str = "Info"
        WARN: str = "Warn"
        ERROR: str = "Error"

    message: str
    level: NotificationLevel


@dataclass
class NotificationEvent(Event):

    data: Optional[NotificationEventData] = None
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

    data: common.CurrentAction = field(default_factory=common.CurrentAction)
    event: str = field(default=wo_suffix(__qualname__), init=False)  # type: ignore  # noqa: F821


# ----------------------------------------------------------------------------------------------------------------------


@dataclass
class PackageStateEvent(Event):

    data: common.PackageState = field(default_factory=common.PackageState)
    event: str = field(default=wo_suffix(__qualname__), init=False)  # type: ignore  # noqa: F821


# ----------------------------------------------------------------------------------------------------------------------


@dataclass
class PackageInfoEvent(Event):

    data: Optional[execution.PackageInfo] = None
    event: str = field(default=wo_suffix(__qualname__), init=False)  # type: ignore  # noqa: F821


# ----------------------------------------------------------------------------------------------------------------------


@dataclass
class ActionStateEvent(Event):

    data: common.ActionState = field(default_factory=common.ActionState)
    event: str = field(default=wo_suffix(__qualname__), init=False)  # type: ignore  # noqa: F821
