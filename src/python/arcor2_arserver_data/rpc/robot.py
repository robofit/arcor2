from dataclasses import dataclass
from typing import Optional

from dataclasses_jsonschema import JsonSchemaMixin

from arcor2.data.common import Joint, Orientation, Pose, Position, StrEnum
from arcor2.data.rpc.common import RPC
from arcor2.exceptions import Arcor2Exception
from arcor2_arserver_data.robot import RobotMeta


class GetRobotMeta(RPC):
    @dataclass
    class Request(RPC.Request):
        pass

    @dataclass
    class Response(RPC.Response):
        data: Optional[list[RobotMeta]] = None


# ----------------------------------------------------------------------------------------------------------------------


class GetRobotJoints(RPC):
    @dataclass
    class Request(RPC.Request):
        @dataclass
        class Args(JsonSchemaMixin):
            robot_id: str
            arm_id: Optional[str] = None

        args: Args

    @dataclass
    class Response(RPC.Response):
        data: Optional[list[Joint]] = None


# ----------------------------------------------------------------------------------------------------------------------


class GetEndEffectorPose(RPC):
    @dataclass
    class Request(RPC.Request):
        @dataclass
        class Args(JsonSchemaMixin):
            robot_id: str
            end_effector_id: str
            arm_id: Optional[str] = None

        args: Args

    @dataclass
    class Response(RPC.Response):
        data: Optional[Pose] = None


# ----------------------------------------------------------------------------------------------------------------------


class GetRobotArms(RPC):
    @dataclass
    class Request(RPC.Request):
        @dataclass
        class Args(JsonSchemaMixin):
            robot_id: str

        args: Args

    @dataclass
    class Response(RPC.Response):
        data: Optional[set[str]] = None


# ----------------------------------------------------------------------------------------------------------------------


class GetEndEffectors(RPC):
    @dataclass
    class Request(RPC.Request):
        @dataclass
        class Args(JsonSchemaMixin):
            robot_id: str
            arm_id: Optional[str]

        args: Args

    @dataclass
    class Response(RPC.Response):
        data: Optional[set[str]] = None


# ----------------------------------------------------------------------------------------------------------------------


class GetGrippers(RPC):
    @dataclass
    class Request(RPC.Request):
        @dataclass
        class Args(JsonSchemaMixin):
            robot_id: str
            arm_id: Optional[str] = None

        args: Args

    @dataclass
    class Response(RPC.Response):
        data: Optional[set[str]] = None


# ----------------------------------------------------------------------------------------------------------------------


class GetSuctions(RPC):
    @dataclass
    class Request(RPC.Request):
        @dataclass
        class Args(JsonSchemaMixin):
            robot_id: str
            arm_id: Optional[str] = None

        args: Args

    @dataclass
    class Response(RPC.Response):
        data: Optional[set[str]] = None


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
        data: Optional[set[str]] = None


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
            safe: bool = True
            linear: bool = False
            arm_id: Optional[str] = None

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
            joints: list[Joint]
            safe: bool = True
            arm_id: Optional[str] = None

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
            safe: bool = True
            linear: bool = False
            arm_id: Optional[str] = None

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
            start_joints: Optional[list[Joint]] = None
            avoid_collisions: bool = True
            arm_id: Optional[str] = None

        args: Args

    @dataclass
    class Response(RPC.Response):
        data: Optional[list[Joint]] = None


# ----------------------------------------------------------------------------------------------------------------------


class ForwardKinematics(RPC):
    @dataclass
    class Request(RPC.Request):
        @dataclass
        class Args(JsonSchemaMixin):
            robot_id: str
            end_effector_id: str
            joints: list[Joint]
            arm_id: Optional[str] = None

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


# ----------------------------------------------------------------------------------------------------------------------


class HandTeachingMode(RPC):
    @dataclass
    class Request(RPC.Request):
        @dataclass
        class Args(JsonSchemaMixin):
            robot_id: str
            enable: bool
            arm_id: Optional[str] = None

        args: Args
        dry_run: bool = False

    @dataclass
    class Response(RPC.Response):
        pass


# ----------------------------------------------------------------------------------------------------------------------


class SetEefPerpendicularToWorld(RPC):
    @dataclass
    class Request(RPC.Request):
        @dataclass
        class Args(JsonSchemaMixin):
            robot_id: str
            end_effector_id: str
            safe: bool = True
            speed: float = 0.25
            linear: bool = True
            arm_id: Optional[str] = None

        args: Args
        dry_run: bool = False

    @dataclass
    class Response(RPC.Response):
        pass


# ----------------------------------------------------------------------------------------------------------------------


class StepRobotEef(RPC):
    @dataclass
    class Request(RPC.Request):
        @dataclass
        class Args(JsonSchemaMixin):
            class Axis(StrEnum):
                X: str = "x"
                Y: str = "y"
                Z: str = "z"

            class What(StrEnum):
                POSITION: str = "position"
                ORIENTATION: str = "orientation"

            class Mode(StrEnum):
                WORLD: str = "world"
                ROBOT: str = "robot"
                USER: str = "user"
                RELATIVE: str = "relative"

            robot_id: str
            end_effector_id: str
            axis: Axis
            what: What
            mode: Mode
            step: float
            safe: bool = True
            pose: Optional[Pose] = None
            speed: float = 0.25
            linear: bool = True
            arm_id: Optional[str] = None

            def __post_init__(self) -> None:
                if self.mode in (self.Mode.USER, self.Mode.RELATIVE) and self.pose is None:
                    raise Arcor2Exception("Pose needed.")

        args: Args
        dry_run: bool = False

    @dataclass
    class Response(RPC.Response):
        pass
