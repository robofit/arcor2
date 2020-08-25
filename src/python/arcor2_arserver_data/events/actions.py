from dataclasses import dataclass, field
from typing import Optional

from dataclasses_jsonschema import JsonSchemaMixin

from arcor2.data.events import Event, wo_suffix


@dataclass
class ActionExecutionData(JsonSchemaMixin):

    action_id: str = ""


@dataclass
class ActionExecutionEvent(Event):
    """Used to notify beginning of the action execution triggered while editing
    a project."""

    data: ActionExecutionData = field(default_factory=ActionExecutionData)
    event: str = field(default=wo_suffix(__qualname__), init=False)  # type: ignore  # noqa: F821


@dataclass
class ActionResult(JsonSchemaMixin):

    action_id: str = ""
    result: Optional[str] = field(default=None, metadata=dict(description="JSON-encoded result of the action."))
    error: Optional[str] = None


@dataclass
class ActionResultEvent(Event):
    """Used to notify result of the action execution triggered while editing a
    project."""

    data: ActionResult = field(default_factory=ActionResult)
    event: str = field(default=wo_suffix(__qualname__), init=False)  # type: ignore  # noqa: F821


@dataclass
class ActionCancelledEvent(Event):
    """Used to notify that the action execution was cancelled."""

    event: str = field(default=wo_suffix(__qualname__), init=False)  # type: ignore  # noqa: F821
