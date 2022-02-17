from dataclasses import dataclass
from typing import Optional

from dataclasses_jsonschema import JsonSchemaMixin

from arcor2.data.common import Position
from arcor2.exceptions import Arcor2Exception


@dataclass
class MeshFocusAction(JsonSchemaMixin):

    mesh_focus_points: list[Position]
    robot_space_points: list[Position]

    def __post_init__(self) -> None:

        if len(self.mesh_focus_points) != len(self.robot_space_points):
            raise Arcor2Exception("Invalid MeshFocusAction.")


@dataclass
class LineCheck(JsonSchemaMixin):

    pt1: Position
    pt2: Position


@dataclass
class LineCheckResult(JsonSchemaMixin):

    safe: bool
    object_id: Optional[str] = None
