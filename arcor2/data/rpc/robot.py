# -*- coding: utf-8 -*-

from typing import List

from dataclasses import dataclass, field

from arcor2.data.robot import RobotMeta
from arcor2.data.rpc.common import Request, Response, wo_suffix


@dataclass
class GetRobotMetaRequest(Request):

    request: str = field(default=wo_suffix(__qualname__), init=False)  # type: ignore  # noqa: F821


@dataclass
class GetRobotMetaResponse(Response):

    data: List[RobotMeta] = field(default_factory=list)
    response: str = field(default=GetRobotMetaRequest.request, init=False)
