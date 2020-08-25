from dataclasses import dataclass, field
from typing import List, Optional

from dataclasses_jsonschema import JsonSchemaMixin

from arcor2.data import common
from arcor2.data.events import Event, wo_suffix


@dataclass
class RobotJointsData(JsonSchemaMixin):

    robot_id: str
    joints: List[common.Joint]


@dataclass
class RobotJointsEvent(Event):

    data: Optional[RobotJointsData] = None
    event: str = field(default=wo_suffix(__qualname__), init=False)  # type: ignore  # noqa: F821


@dataclass
class EefPose(JsonSchemaMixin):

    end_effector_id: str
    pose: common.Pose


@dataclass
class RobotEefData(JsonSchemaMixin):

    robot_id: str
    end_effectors: List[EefPose] = field(default_factory=list)


@dataclass
class RobotEefEvent(Event):

    data: Optional[RobotEefData] = None
    event: str = field(default=wo_suffix(__qualname__), init=False)  # type: ignore  # noqa: F821


# ----------------------------------------------------------------------------------------------------------------------


class MoveEventType(common.StrEnum):
    START: str = "start"
    END: str = "end"
    FAILED: str = "failed"


@dataclass
class RobotMoveToData(JsonSchemaMixin):

    move_event_type: MoveEventType
    robot_id: str


@dataclass
class RobotMoveToPoseData(RobotMoveToData):

    end_effector_id: str
    target_pose: common.Pose
    message: Optional[str] = None


@dataclass
class RobotMoveToPoseEvent(Event):

    data: Optional[RobotMoveToPoseData] = None
    event: str = field(default=wo_suffix(__qualname__), init=False)  # type: ignore  # noqa: F821


# ----------------------------------------------------------------------------------------------------------------------


@dataclass
class RobotMoveToJointsData(RobotMoveToData):

    target_joints: List[common.Joint]
    message: Optional[str] = None


@dataclass
class RobotMoveToJointsEvent(Event):

    data: Optional[RobotMoveToJointsData] = None
    event: str = field(default=wo_suffix(__qualname__), init=False)  # type: ignore  # noqa: F821


# ----------------------------------------------------------------------------------------------------------------------


@dataclass
class RobotMoveToActionPointOrientationData(RobotMoveToData):

    end_effector_id: str
    orientation_id: str
    message: Optional[str] = None


@dataclass
class RobotMoveToActionPointOrientationEvent(Event):

    data: Optional[RobotMoveToActionPointOrientationData] = None
    event: str = field(default=wo_suffix(__qualname__), init=False)  # type: ignore  # noqa: F821


# ----------------------------------------------------------------------------------------------------------------------


@dataclass
class RobotMoveToActionPointJointsData(RobotMoveToData):

    joints_id: str
    message: Optional[str] = None


@dataclass
class RobotMoveToActionPointJointsEvent(Event):

    data: Optional[RobotMoveToActionPointJointsData] = None
    event: str = field(default=wo_suffix(__qualname__), init=False)  # type: ignore  # noqa: F821
