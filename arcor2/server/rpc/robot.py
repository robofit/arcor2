from typing import Union

from arcor2.data import rpc
from arcor2 import helpers as hlp

from arcor2.server import globals as glob


async def get_robot_meta_cb(req: rpc.robot.GetRobotMetaRequest) -> Union[rpc.robot.GetRobotMetaResponse,
                                                                         hlp.RPC_RETURN_TYPES]:

    return rpc.robot.GetRobotMetaResponse(data=list(glob.ROBOT_META.values()))
