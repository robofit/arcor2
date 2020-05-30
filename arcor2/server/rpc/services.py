#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from websockets.server import WebSocketServerProtocol as WsClient

from arcor2.data import rpc
from arcor2.server import globals as glob


async def get_services_cb(req: rpc.services.GetServicesRequest, ui: WsClient) -> rpc.services.GetServicesResponse:
    return rpc.services.GetServicesResponse(data=list(glob.SERVICE_TYPES.values()))
