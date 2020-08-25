from dataclasses import dataclass
from typing import List

from dataclasses_jsonschema import JsonSchemaMixin

from arcor2.data.common import Position
from arcor2.exceptions import Arcor2Exception


@dataclass
class MeshFocusAction(JsonSchemaMixin):

    mesh_focus_points: List[Position]
    robot_space_points: List[Position]

    def __post_init__(self) -> None:

        if len(self.mesh_focus_points) != len(self.robot_space_points):
            raise Arcor2Exception("Invalid MeshFocusAction.")
