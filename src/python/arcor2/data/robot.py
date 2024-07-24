from dataclasses import dataclass
from typing import Optional

from dataclasses_jsonschema import JsonSchemaMixin

from arcor2.data.common import Joint, Pose, StrEnum


class RobotType(StrEnum):
    ARTICULATED = "articulated"  # typically a 6 DoF robot
    CARTESIAN = "cartesian"
    SCARA = "scara"  # ...or scara-like


@dataclass
class InverseKinematicsRequest(JsonSchemaMixin):
    pose: Pose
    start_joints: Optional[list[Joint]] = None
    avoid_collisions: bool = True
