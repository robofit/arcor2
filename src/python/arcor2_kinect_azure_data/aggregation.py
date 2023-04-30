from dataclasses import dataclass

from dataclasses_jsonschema import JsonSchemaMixin

from arcor2.data.common import Orientation, Position


@dataclass
class MovingDirection(JsonSchemaMixin):
    position: Position = Position()
    speed: Position = Position()
    orientation_speed: Orientation = Orientation()


__all__ = ["MovingDirection"]
