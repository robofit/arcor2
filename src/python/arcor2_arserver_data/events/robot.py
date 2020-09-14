from dataclasses import dataclass, field
from typing import List, Optional

from dataclasses_jsonschema import JsonSchemaMixin

from arcor2.data import common
from arcor2.data.events import Event


@dataclass
class RobotJoints(Event):
    @dataclass
    class Data(JsonSchemaMixin):
        robot_id: str
        joints: List[common.Joint]

    data: Data


@dataclass
class RobotEef(Event):
    @dataclass
    class Data(JsonSchemaMixin):
        @dataclass
        class EefPose(JsonSchemaMixin):
            end_effector_id: str
            pose: common.Pose

        robot_id: str
        end_effectors: List[EefPose] = field(default_factory=list)

    data: Data


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
        message: Optional[str] = None

    data: Data


# ----------------------------------------------------------------------------------------------------------------------


@dataclass
class RobotMoveToJoints(Event):
    @dataclass
    class Data(RobotMoveToData):
        target_joints: List[common.Joint]
        message: Optional[str] = None

    data: Data


# ----------------------------------------------------------------------------------------------------------------------


@dataclass
class RobotMoveToActionPointOrientation(Event):
    @dataclass
    class Data(RobotMoveToData):
        end_effector_id: str
        orientation_id: str
        message: Optional[str] = None

    data: Data


# ----------------------------------------------------------------------------------------------------------------------


@dataclass
class RobotMoveToActionPointJoints(Event):
    @dataclass
    class Data(RobotMoveToData):
        joints_id: str
        message: Optional[str] = None

    data: Data
