import asyncio

from websockets.server import WebSocketServerProtocol as WsClient

from arcor2.cached import UpdateableCachedScene
from arcor2.exceptions import Arcor2Exception
from arcor2.helpers import run_in_executor
from arcor2.image import image_to_str
from arcor2.object_types.abstract import Camera
from arcor2_arserver import globals as glob
from arcor2_arserver import logger
from arcor2_arserver import notifications as notif
from arcor2_arserver.helpers import ensure_write_locked
from arcor2_arserver.scene import ensure_scene_started, get_instance, update_scene_object_pose
from arcor2_arserver_data.events.common import ProcessState
from arcor2_arserver_data.rpc.camera import CalibrateCamera, CameraColorImage, CameraColorParameters
from arcor2_calibration_data import client as calib_client


async def camera_color_image_cb(req: CameraColorImage.Request, ui: WsClient) -> CameraColorImage.Response:

    glob.LOCK.scene_or_exception()

    await ensure_write_locked(req.args.id, glob.USERS.user_name(ui))

    ensure_scene_started()
    camera = get_instance(req.args.id, Camera)
    resp = CameraColorImage.Response()
    resp.data = image_to_str(camera.color_image())
    return resp


async def camera_color_parameters_cb(
    req: CameraColorParameters.Request, ui: WsClient
) -> CameraColorParameters.Response:

    glob.LOCK.scene_or_exception()

    await ensure_write_locked(req.args.id, glob.USERS.user_name(ui))

    ensure_scene_started()
    camera = get_instance(req.args.id, Camera)
    resp = CameraColorParameters.Response()
    resp.data = camera.color_camera_params
    return resp


CAMERA_CALIB = "CameraCalibration"


async def calibrate_camera(scene: UpdateableCachedScene, camera: Camera) -> None:

    assert camera.color_camera_params

    await notif.broadcast_event(ProcessState(ProcessState.Data(CAMERA_CALIB, ProcessState.Data.StateEnum.Started)))
    try:
        img = await run_in_executor(camera.color_image)
        estimated_pose = await run_in_executor(calib_client.estimate_camera_pose, camera.color_camera_params, img)
    except Arcor2Exception as e:
        await notif.broadcast_event(
            ProcessState(ProcessState.Data(CAMERA_CALIB, ProcessState.Data.StateEnum.Failed, str(e)))
        )
        logger.exception("Failed to calibrate the camera.")
        return

    await update_scene_object_pose(scene, scene.object(camera.id), estimated_pose.pose, camera)
    await notif.broadcast_event(ProcessState(ProcessState.Data(CAMERA_CALIB, ProcessState.Data.StateEnum.Finished)))


async def calibrate_camera_cb(req: CalibrateCamera.Request, ui: WsClient) -> None:

    scene = glob.LOCK.scene_or_exception()

    ensure_scene_started()
    camera = get_instance(req.args.id, Camera)

    # TODO check camera features / meta if it supports getting color image
    if not camera.color_camera_params:
        raise Arcor2Exception("Camera parameters not available.")

    await ensure_write_locked(req.args.id, glob.USERS.user_name(ui))

    asyncio.ensure_future(calibrate_camera(scene, camera))
