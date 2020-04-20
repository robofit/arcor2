from typing import Union

from arcor2.data import rpc
from arcor2 import helpers as hlp

from arcor2.server import globals as glob
from arcor2.server.robot import get_robot_joints, get_end_effector_pose
from arcor2.server.decorators import scene_needed


async def get_robot_meta_cb(req: rpc.robot.GetRobotMetaRequest) -> Union[rpc.robot.GetRobotMetaResponse,
                                                                         hlp.RPC_RETURN_TYPES]:

    return rpc.robot.GetRobotMetaResponse(data=list(glob.ROBOT_META.values()))


@scene_needed
async def get_robot_joints_cb(req: rpc.robot.GetRobotJointsRequest) -> Union[rpc.robot.GetRobotJointsResponse,
                                                                             hlp.RPC_RETURN_TYPES]:

    return rpc.robot.GetRobotJointsResponse(data=await get_robot_joints(req.args.robot_id))


@scene_needed
async def get_end_effector_pose_cb(req: rpc.robot.GetEndEffectorPoseRequest) -> \
        Union[rpc.robot.GetEndEffectorPoseResponse, hlp.RPC_RETURN_TYPES]:

    return rpc.robot.GetEndEffectorPoseResponse(data=await get_end_effector_pose(req.args.robot_id,
                                                                                 req.args.end_effector_id))
