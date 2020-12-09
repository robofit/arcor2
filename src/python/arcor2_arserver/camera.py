from arcor2.exceptions import Arcor2Exception
from arcor2.object_types.abstract import Camera
from arcor2_arserver.scene import get_instance


def get_camera_instance(obj_id: str) -> Camera:

    obj = get_instance(obj_id)

    if not isinstance(obj, Camera):
        raise Arcor2Exception("Not a camera.")

    return obj
