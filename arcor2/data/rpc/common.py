from dataclasses import dataclass, field
from typing import Optional, List, Tuple, Set
import re
from enum import Enum

from dataclasses_jsonschema import JsonSchemaMixin

"""
mypy does not recognize __qualname__ so far: https://github.com/python/mypy/issues/6473
flake8 sucks here as well: https://bugs.launchpad.net/pyflakes/+bug/1648651
TODO: remove type: ignore once it is fixed
"""


def wo_suffix(name: str) -> str:
    return re.sub('Request$', '', name)


class ChangeType(Enum):

    ADD: str = "add"
    UPDATE: str = "update"
    DELETE: str = "delete"


@dataclass
class Request(JsonSchemaMixin):

    id: int
    request: str


@dataclass
class Response(JsonSchemaMixin):

    response: str = ""
    id: int = 0
    result: bool = True
    messages: Optional[List[str]] = None


# ----------------------------------------------------------------------------------------------------------------------

@dataclass
class TypeArgs(JsonSchemaMixin):
    type: str


@dataclass
class IdArgs(JsonSchemaMixin):
    id: str


@dataclass
class RobotArg(JsonSchemaMixin):
    robot_id: str = field(metadata=dict(description="Object id of the robot or robot_id within the robot service."))
    end_effector: str

    def as_tuple(self) -> Tuple[str, str]:
        return self.robot_id, self.end_effector


# ----------------------------------------------------------------------------------------------------------------------

@dataclass
class SystemInfoRequest(Request):

    request: str = field(default=wo_suffix(__qualname__), init=False)  # type: ignore  # noqa: F821


@dataclass
class SystemInfoData(JsonSchemaMixin):

    version: str = ""
    api_version: str = ""
    supported_parameter_types: Set[str] = field(default_factory=set)
    supported_rpc_requests: Set[str] = field(default_factory=set)


@dataclass
class SystemInfoResponse(Response):

    data: SystemInfoData = field(default_factory=SystemInfoData)
    response: str = field(default=SystemInfoRequest.request, init=False)
