from dataclasses import dataclass, field
from typing import Optional

from dataclasses_jsonschema import JsonSchemaMixin

from arcor2.data.robot import RobotType


@dataclass
class RobotFeatures(JsonSchemaMixin):
    """Names of the robot features must match names of the methods."""

    move_to_pose: bool = False
    move_to_joints: bool = False
    stop: bool = False
    forward_kinematics: bool = False
    inverse_kinematics: bool = False
    hand_teaching: bool = False


@dataclass
class RobotMeta(JsonSchemaMixin):
    """Robot meta that could be extracted without creating an instance."""

    type: str
    robot_type: RobotType
    multi_arm: bool = False
    features: RobotFeatures = field(default_factory=RobotFeatures)
    urdf_package_filename: Optional[str] = None
