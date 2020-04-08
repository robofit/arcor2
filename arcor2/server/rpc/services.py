#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from arcor2.data import rpc

from arcor2.server import globals as glob


async def get_services_cb(req: rpc.services.GetServicesRequest) -> rpc.services.GetServicesResponse:
    return rpc.services.GetServicesResponse(data=list(glob.SERVICE_TYPES.values()))
