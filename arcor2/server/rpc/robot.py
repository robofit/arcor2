

async def get_robot_meta_cb(req: rpc.robot.GetRobotMetaRequest) -> Union[rpc.robot.GetRobotMetaResponse,
                                                                         hlp.RPC_RETURN_TYPES]:

    return rpc.robot.GetRobotMetaResponse(data=list(ROBOT_META.values()))