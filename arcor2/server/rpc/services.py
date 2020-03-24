

async def get_services_cb(req: rpc.services.GetServicesRequest) -> rpc.services.GetServicesResponse:
    return rpc.services.GetServicesResponse(data=list(SERVICE_TYPES.values()))