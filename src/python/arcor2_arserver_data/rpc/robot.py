from dataclasses import dataclass
from typing import List, Optional, Set

from dataclasses_jsonschema import JsonSchemaMixin

from arcor2.data.common import Joint, Orientation, Pose, Position, StrEnum
from arcor2.data.rpc.common import RPC
from arcor2_arserver_data.robot import RobotMeta


class GetRobotMeta(RPC):
    @dataclass
    class Request(RPC.Request):
        pass

    @dataclass
    class Response(RPC.Response):
        data: Optional[List[RobotMeta]] = None


# ----------------------------------------------------------------------------------------------------------------------


class GetRobotJoints(RPC):
    @dataclass
    class Request(RPC.Request):
        @dataclass
        class Args(JsonSchemaMixin):
            robot_id: str

        args: Args

    @dataclass
    class Response(RPC.Response):
        data: Optional[List[Joint]] = None


# ----------------------------------------------------------------------------------------------------------------------


class GetEndEffectorPose(RPC):
    @dataclass
    class Request(RPC.Request):
        @dataclass
        class Args(JsonSchemaMixin):
            robot_id: str
            end_effector_id: str

        args: Args

    @dataclass
    class Response(RPC.Response):
        data: Optional[Pose] = None


# ----------------------------------------------------------------------------------------------------------------------


class GetEndEffectors(RPC):
    @dataclass
    class Request(RPC.Request):
        @dataclass
        class Args(JsonSchemaMixin):
            robot_id: str

        args: Args

    @dataclass
    class Response(RPC.Response):
        data: Optional[Set[str]] = None


# ----------------------------------------------------------------------------------------------------------------------


class GetGrippers(RPC):
    @dataclass
    class Request(RPC.Request):
        @dataclass
        class Args(JsonSchemaMixin):
            robot_id: str

        args: Args

    @dataclass
    class Response(RPC.Response):
        data: Optional[Set[str]] = None


# ----------------------------------------------------------------------------------------------------------------------


class GetSuctions(RPC):
    @dataclass
    class Request(RPC.Request):
        @dataclass
        class Args(JsonSchemaMixin):
            robot_id: str

        args: Args

    @dataclass
    class Response(RPC.Response):
        data: Optional[Set[str]] = None


# ----------------------------------------------------------------------------------------------------------------------


class RegisterForRobotEvent(RPC):
    @dataclass
    class Request(RPC.Request):
        @dataclass
        class Args(JsonSchemaMixin):
            class RegisterEnum(StrEnum):
                EEF_POSE: str = "eef_pose"
                JOINTS: str = "joints"

            robot_id: str
            what: RegisterEnum
            send: bool

        args: Args

    @dataclass
    class Response(RPC.Response):
        data: Optional[Set[str]] = None


# ----------------------------------------------------------------------------------------------------------------------


class MoveToPose(RPC):
    @dataclass
    class Request(RPC.Request):
        @dataclass
        class Args(JsonSchemaMixin):
            robot_id: str
            end_effector_id: str
            speed: float
            position: Optional[Position]
            orientation: Optional[Orientation]

        args: Args

    @dataclass
    class Response(RPC.Response):
        pass


# ----------------------------------------------------------------------------------------------------------------------


class StopRobot(RPC):
    @dataclass
    class Request(RPC.Request):
        @dataclass
        class Args(JsonSchemaMixin):
            robot_id: str

        args: Args

    @dataclass
    class Response(RPC.Response):
        pass


# ----------------------------------------------------------------------------------------------------------------------


class MoveToJoints(RPC):
    @dataclass
    class Request(RPC.Request):
        @dataclass
        class Args(JsonSchemaMixin):
            robot_id: str
            speed: float
            joints: List[Joint]

        args: Args

    @dataclass
    class Response(RPC.Response):
        pass


# ----------------------------------------------------------------------------------------------------------------------


class MoveToActionPoint(RPC):
    @dataclass
    class Request(RPC.Request):
        @dataclass
        class Args(JsonSchemaMixin):
            robot_id: str
            speed: float
            end_effector_id: Optional[str] = None
            orientation_id: Optional[str] = None
            joints_id: Optional[str] = None

        args: Args

    @dataclass
    class Response(RPC.Response):
        pass


# ----------------------------------------------------------------------------------------------------------------------


class InverseKinematics(RPC):
    @dataclass
    class Request(RPC.Request):
        @dataclass
        class Args(JsonSchemaMixin):
            robot_id: str
            end_effector_id: str
            pose: Pose
            start_joints: Optional[List[Joint]] = None
            avoid_collisions: bool = True

        args: Args

    @dataclass
    class Response(RPC.Response):
        data: Optional[List[Joint]] = None


# ----------------------------------------------------------------------------------------------------------------------


class ForwardKinematics(RPC):
    @dataclass
    class Request(RPC.Request):
        @dataclass
        class Args(JsonSchemaMixin):
            robot_id: str
            end_effector_id: str
            joints: List[Joint]

        args: Args

    @dataclass
    class Response(RPC.Response):
        data: Optional[Pose] = None


# ----------------------------------------------------------------------------------------------------------------------


class CalibrateRobot(RPC):
    @dataclass
    class Request(RPC.Request):
        @dataclass
        class Args(JsonSchemaMixin):
            robot_id: str
            camera_id: Optional[str] = None
            move_to_calibration_pose: bool = True

        args: Args

    @dataclass
    class Response(RPC.Response):
        pass
