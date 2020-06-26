# -*- coding: utf-8 -*-

from dataclasses import dataclass, field
from typing import List

from arcor2.data.rpc.common import Request, Response, wo_suffix
from arcor2.data.services import ServiceTypeMeta


@dataclass
class GetServicesRequest(Request):

    request: str = field(default=wo_suffix(__qualname__), init=False)  # type: ignore  # noqa: F821


@dataclass
class GetServicesResponse(Response):

    data: List[ServiceTypeMeta] = field(default_factory=list)
    response: str = field(default=GetServicesRequest.request, init=False)
