from dataclasses import dataclass
from typing import Optional

from dataclasses_jsonschema import JsonSchemaMixin

from arcor2.data import common
from arcor2.data.events import Event

# ----------------------------------------------------------------------------------------------------------------------


@dataclass
class RobotMoveToData(JsonSchemaMixin):
    class MoveEventType(common.StrEnum):
        START: str = "start"
        END: str = "end"
        FAILED: str = "failed"

    move_event_type: MoveEventType
    robot_id: str


@dataclass
class RobotMoveToPose(Event):
    @dataclass
    class Data(RobotMoveToData):
        end_effector_id: str
        target_pose: common.Pose
        safe: bool
        linear: bool
        message: Optional[str] = None
        arm_id: Optional[str] = None

    data: Data


# ----------------------------------------------------------------------------------------------------------------------


@dataclass
class RobotMoveToJoints(Event):
    @dataclass
    class Data(RobotMoveToData):
        target_joints: list[common.Joint]
        safe: bool
        message: Optional[str] = None
        arm_id: Optional[str] = None

    data: Data


# ----------------------------------------------------------------------------------------------------------------------


@dataclass
class RobotMoveToActionPointOrientation(Event):
    @dataclass
    class Data(RobotMoveToData):
        end_effector_id: str
        orientation_id: str
        safe: bool
        linear: bool
        message: Optional[str] = None
        arm_id: Optional[str] = None

    data: Data


# ----------------------------------------------------------------------------------------------------------------------


@dataclass
class RobotMoveToActionPointJoints(Event):
    @dataclass
    class Data(RobotMoveToData):
        joints_id: str
        safe: bool
        message: Optional[str] = None
        arm_id: Optional[str] = None

    data: Data


# ----------------------------------------------------------------------------------------------------------------------


@dataclass
class HandTeachingMode(Event):
    @dataclass
    class Data(JsonSchemaMixin):
        robot_id: str
        enabled: bool
        arm_id: Optional[str] = None

    data: Data
