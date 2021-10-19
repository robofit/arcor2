#!/usr/bin/env python3

import argparse
import io
import os
import zipfile
from functools import wraps
from typing import TYPE_CHECKING, Optional

from arcor2_kinect_azure import get_data, version
from flask import jsonify, request, send_file
from PIL import Image

from arcor2 import env
from arcor2.data.camera import CameraParameters
from arcor2.flask import RespT, create_app, run_app
from arcor2.helpers import port_from_url
from arcor2.image import image_to_bytes_io
from arcor2.logging import get_logger

logger = get_logger(__name__)

URL = os.getenv("ARCOR2_KINECT_AZURE_URL", "http://localhost:5016")
SERVICE_NAME = "Kinect Azure Service"

app = create_app(__name__)

if TYPE_CHECKING:
    from arcor2_kinect_azure.kinect_azure import KinectAzure

_kinect: Optional["KinectAzure"] = None
_mock: bool = False
_mock_started: bool = False


def started() -> bool:

    if _mock:
        return _mock_started

    return _kinect is not None


def requires_started(f):
    @wraps(f)
    def wrapped(*args, **kwargs):
        if not started():
            return "Not started", 403
        return f(*args, **kwargs)

    return wrapped


def color_image() -> Image.Image:

    return Image.open(get_data("rgb.jpg"))


def depth_image() -> Image.Image:

    return Image.open(get_data("depth.png"))


@app.route("/state/start", methods=["PUT"])
def put_start() -> RespT:
    """Start the sensor.
    ---
    put:
        description: Start the sensor.
        tags:
           - State
        responses:
            200:
              description: Ok
            403:
              description: Already started
    """

    if started():
        return "Already started.", 403

    if _mock:
        global _mock_started
        _mock_started = True
    else:

        # lazy import so mock mode can work without pyk4a installed
        from arcor2_kinect_azure.kinect_azure import KinectAzure

        global _kinect
        assert _kinect is None
        _kinect = KinectAzure()

    return "ok", 200


@app.route("/state/stop", methods=["PUT"])
@requires_started
def put_stop() -> RespT:
    """Stop the sensor.
    ---
    put:
        description: Stop the sensor.
        tags:
           - State
        responses:
            200:
              description: Ok
            403:
              description: Not started
    """

    if _mock:
        global _mock_started
        _mock_started = False
    else:
        global _kinect
        assert _kinect is not None
        _kinect.cleanup()
        _kinect = None
    return "ok", 200


@app.route("/state/started", methods=["GET"])
def get_started() -> RespT:
    """Get the current state.
    ---
    get:
        description: Get the current state.
        tags:
           - State
        responses:
            200:
              description: Ok
              content:
                application/json:
                    schema:
                        type: boolean
            403:
              description: Not started
    """

    return jsonify(started()), 200


@app.route("/color/image", methods=["GET"])
@requires_started
def get_image_color() -> RespT:
    """Get the color image.
    ---
    get:
        description: Get the color image.
        tags:
           - Color camera
        responses:
            200:
              description: Ok
              content:
                image/jpeg:
                    schema:
                        type: string
            403:
              description: Not started
    """

    if _mock:
        img = color_image()
    else:
        assert _kinect is not None
        img = _kinect.color_image()

    return send_file(
        image_to_bytes_io(img, target_format="JPEG", target_mode="RGB"),
        mimetype="image/jpeg",
        max_age=0,
    )


@app.route("/color/parameters", methods=["GET"])
@requires_started
def get_color_camera_parameters() -> RespT:
    """Get the color camera parameters.
    ---
    get:
        description: Get the color camera parameters.
        tags:
           - Color camera
        responses:
            200:
              description: Ok
              content:
                application/json:
                  schema:
                    $ref: CameraParameters
            403:
              description: Not started
    """

    if _mock:
        params = CameraParameters(
            915.575, 915.425, 957.69, 556.35, [0.447, -2.5, 0.00094, -0.00053, 1.432, 0.329, -2.332, 1.363]
        )
    else:
        assert _kinect is not None

        if not _kinect.color_camera_params:
            return "Failed to get camera parameters", 403

        params = _kinect.color_camera_params

    return jsonify(params.to_dict()), 200


@app.route("/depth/image", methods=["GET"])
@requires_started
def get_image_depth() -> RespT:
    """Get the depth image.
    ---
    get:
        description: Get the depth image.
        tags:
           - Depth camera
        parameters:
           - in: query
             name: averagedFrames
             schema:
                type: integer
                default: 1
             required: false
             description: Package name
        responses:
            200:
              description: Ok
              content:
                image/png:
                    schema:
                        type: string
            403:
              description: Not started
    """

    if _mock:
        img = depth_image()
    else:
        assert _kinect is not None
        img = _kinect.depth_image(averaged_frames=int(request.args.get("averagedFrames", default=1)))

    return send_file(image_to_bytes_io(img, target_format="PNG"), mimetype="image/png", max_age=0)


@app.route("/synchronized/image", methods=["GET"])
@requires_started
def get_image_both() -> RespT:
    """Get the both color/depth image.
    ---
    get:
        description: Get the depth image.
        tags:
           - Synchronized
        responses:
            200:
              description: Ok
              content:
                application/zip:
                    schema:
                      type: string
                      format: binary
            403:
              description: Not started
    """

    if _mock:
        color = color_image()
        depth = depth_image()
    else:
        assert _kinect is not None
        both = _kinect.sync_images()
        color = both.color
        depth = both.depth

    mem_zip = io.BytesIO()

    with zipfile.ZipFile(mem_zip, mode="w", compression=zipfile.ZIP_STORED) as zf:
        zf.writestr("color.jpg", image_to_bytes_io(color).getvalue())
        zf.writestr("depth.png", image_to_bytes_io(depth, target_format="PNG").getvalue())

    mem_zip.seek(0)
    return send_file(
        mem_zip, mimetype="application/zip", max_age=0, as_attachment=True, download_name="synchronized.zip"
    )


def main() -> None:

    parser = argparse.ArgumentParser(description=SERVICE_NAME)
    parser.add_argument("-s", "--swagger", action="store_true", default=False)
    parser.add_argument("-m", "--mock", action="store_true", default=env.get_bool("ARCOR2_KINECT_AZURE_MOCK"))
    args = parser.parse_args()

    global _mock
    _mock = args.mock
    if _mock:
        logger.info("Starting as a mock!")

    run_app(app, SERVICE_NAME, version(), version(), port_from_url(URL), [CameraParameters], args.swagger)

    if _kinect:
        _kinect.cleanup()


if __name__ == "__main__":
    main()
