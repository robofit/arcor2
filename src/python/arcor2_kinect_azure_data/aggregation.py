from dataclasses import dataclass, field

from dataclasses_jsonschema import JsonSchemaMixin

from arcor2.data.common import Orientation, Position


@dataclass
class MovingDirection(JsonSchemaMixin):
    position: Position = field(default_factory=Position)
    speed: Position = field(default_factory=Position)
    orientation_speed: Orientation = field(default_factory=Orientation)


__all__ = ["MovingDirection"]
