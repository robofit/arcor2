from dataclasses import dataclass, field
from typing import NamedTuple, Optional

from dataclasses_jsonschema import JsonSchemaMixin


class Arcor2Mixin(JsonSchemaMixin):
    @classmethod
    def get_qualname(cls) -> str:
        return cls.__qualname__.split(".")[0]


class RPC:
    """Base class for all RPCs."""

    @dataclass
    class Request(Arcor2Mixin):  # TODO from_dict -> check that request key is == to qualname

        id: int
        request: str = field(init=False)

        def __post_init__(self) -> None:
            self.request = self.get_qualname()

    @dataclass
    class Response(Arcor2Mixin):

        id: int = 0
        response: str = field(init=False)
        result: bool = True
        messages: Optional[list[str]] = None
        # TODO define data here somehow? And check that if result==True there are some data

        def __post_init__(self) -> None:
            self.response = self.get_qualname()


# ----------------------------------------------------------------------------------------------------------------------


@dataclass
class TypeArgs(JsonSchemaMixin):
    type: str


@dataclass
class IdArgs(JsonSchemaMixin):
    id: str


@dataclass
class RobotArg(JsonSchemaMixin):
    class RobotArgTuple(NamedTuple):

        robot_id: str
        end_effector: str
        arm_id: Optional[str] = None

    robot_id: str = field(metadata=dict(description="Object id of the robot or robot_id within the robot service."))
    end_effector: str
    arm_id: Optional[str] = None

    def as_tuple(self) -> RobotArgTuple:
        return self.RobotArgTuple(self.robot_id, self.end_effector, self.arm_id)


# ----------------------------------------------------------------------------------------------------------------------


class Version(RPC):
    @dataclass
    class Request(RPC.Request):
        pass

    @dataclass
    class Response(RPC.Response):
        @dataclass
        class Data(JsonSchemaMixin):
            version: str = ""

        data: Optional[Data] = None
