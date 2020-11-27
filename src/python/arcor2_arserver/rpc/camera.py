import asyncio

from arcor2_calibration_data import client as calib_client
from websockets.server import WebSocketServerProtocol as WsClient

from arcor2.data.events import Event
from arcor2.exceptions import Arcor2Exception
from arcor2.image import image_to_str
from arcor2.object_types.abstract import Camera
from arcor2_arserver import globals as glob
from arcor2_arserver import notifications as notif
from arcor2_arserver.decorators import scene_needed
from arcor2_arserver.scene import ensure_scene_started, get_instance, set_object_pose
from arcor2_arserver_data.events.scene import SceneObjectChanged
from arcor2_arserver_data.rpc.camera import CalibrateCamera, CameraColorImage, CameraColorParameters


def get_camera_instance(obj_id: str) -> Camera:

    obj = get_instance(obj_id)

    if not isinstance(obj, Camera):
        raise Arcor2Exception("Not a camera.")

    return obj


@scene_needed
async def camera_color_image_cb(req: CameraColorImage.Request, ui: WsClient) -> CameraColorImage.Response:

    assert glob.SCENE

    ensure_scene_started()
    camera = get_camera_instance(req.args.id)
    resp = CameraColorImage.Response()
    resp.data = image_to_str(camera.color_image())
    return resp


@scene_needed
async def camera_color_parameters_cb(
    req: CameraColorParameters.Request, ui: WsClient
) -> CameraColorParameters.Response:

    assert glob.SCENE

    ensure_scene_started()
    camera = get_camera_instance(req.args.id)
    resp = CameraColorParameters.Response()
    resp.data = camera.color_camera_params
    return resp


@scene_needed
async def calibrate_camera_cb(req: CalibrateCamera.Request, ui: WsClient) -> None:

    assert glob.SCENE

    ensure_scene_started()
    camera = get_camera_instance(req.args.id)

    try:
        img = camera.color_image()
    except NotImplementedError as e:
        raise Arcor2Exception("Camera does not support getting color images.") from e

    if not camera.color_camera_params:
        raise Arcor2Exception("Camera parameters not available.")

    pose = calib_client.estimate_camera_pose(camera.color_camera_params, img)

    asyncio.ensure_future(set_object_pose(camera, pose))

    scene_obj = glob.SCENE.object(req.args.id)
    scene_obj.pose = pose
    glob.SCENE.update_modified()

    evt = SceneObjectChanged(scene_obj)
    evt.change_type = Event.Type.UPDATE
    asyncio.ensure_future(notif.broadcast_event(evt))
