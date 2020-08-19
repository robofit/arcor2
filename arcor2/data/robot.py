from dataclasses import dataclass, field
from typing import Optional

from dataclasses_jsonschema import JsonSchemaMixin

from arcor2.data.common import StrEnum


class RobotType(StrEnum):

    ARTICULATED = "articulated"  # typically a 6 DoF robot
    CARTESIAN = "cartesian"
    SCARA = "scara"  # ...or scara-like


@dataclass
class RobotFeatures(JsonSchemaMixin):

    move_to_pose: bool = False
    move_to_joints: bool = False
    stop: bool = False


@dataclass
class RobotMeta(JsonSchemaMixin):
    """
    Robot meta that could be extracted without creating an instance.
    """

    type: str
    robot_type: RobotType
    features: RobotFeatures = field(default_factory=RobotFeatures)
    urdf_package_filename: Optional[str] = None
