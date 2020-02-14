# -*- coding: utf-8 -*-

from dataclasses import dataclass, field

from arcor2.data.object_type import MeshList
from arcor2.data.rpc.common import Request, Response, wo_suffix


@dataclass
class ListMeshesRequest(Request):

    request: str = field(default=wo_suffix(__qualname__), init=False)  # type: ignore  # noqa: F821


@dataclass
class ListMeshesResponse(Response):

    data: MeshList = field(default_factory=list)
    response: str = field(default=ListMeshesRequest.request, init=False)
