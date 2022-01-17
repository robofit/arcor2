from dataclasses import dataclass, field
from typing import Optional

from dataclasses_jsonschema import JsonSchemaMixin

from arcor2.data.events import Event


@dataclass
class ActionExecution(Event):
    """Used to notify beginning of the action execution triggered while editing
    a project."""

    @dataclass
    class Data(JsonSchemaMixin):
        action_id: str = ""

    data: Data


@dataclass
class ActionResult(Event):
    """Used to notify result of the action execution triggered while editing a
    project."""

    @dataclass
    class Data(JsonSchemaMixin):
        action_id: str
        results: Optional[list[str]] = field(
            default=None, metadata=dict(description="JSON-encoded results of the action.")
        )
        error: Optional[str] = None

    data: Data


@dataclass
class ActionCancelled(Event):
    """Used to notify that the action execution was cancelled."""

    pass
