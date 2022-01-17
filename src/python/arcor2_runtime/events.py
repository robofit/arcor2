from dataclasses import dataclass, field
from typing import Optional

from dataclasses_jsonschema import JsonSchemaMixin

from arcor2.data.common import Joint, Pose
from arcor2.data.events import Event


@dataclass
class RobotJoints(Event):
    @dataclass
    class Data(JsonSchemaMixin):
        robot_id: str
        joints: list[Joint]

    data: Data


@dataclass
class RobotEef(Event):
    @dataclass
    class Data(JsonSchemaMixin):
        @dataclass
        class EefPose(JsonSchemaMixin):
            end_effector_id: str
            pose: Pose
            arm_id: Optional[str] = None

        robot_id: str
        end_effectors: list[EefPose] = field(default_factory=list)

    data: Data
