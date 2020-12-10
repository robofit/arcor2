#!/usr/bin/env python3

import argparse
import io
import json
import os
import zipfile
from functools import wraps
from typing import Optional, Tuple

from apispec import APISpec
from apispec_webframeworks.flask import FlaskPlugin
from arcor2_kinect_azure import version
from arcor2_kinect_azure.kinect_azure import KinectAzure
from dataclasses_jsonschema.apispec import DataclassesPlugin
from flask import Flask, Response, jsonify, request, send_file
from flask_cors import CORS
from flask_swagger_ui import get_swaggerui_blueprint
from PIL import Image

from arcor2.data.camera import CameraParameters
from arcor2.helpers import port_from_url
from arcor2.image import image_to_bytes_io
from arcor2.logging import get_logger

logger = get_logger(__name__)

URL = os.getenv("ARCOR2_KINECT_AZURE_URL", "http://localhost:5016")
SERVICE_NAME = "Kinect Azure Service"

# Create an APISpec
spec = APISpec(
    title=SERVICE_NAME,
    version=version(),
    openapi_version="3.0.2",
    plugins=[FlaskPlugin(), DataclassesPlugin()],
)

app = Flask(__name__)
CORS(app)

_kinect: Optional[KinectAzure] = None
_mock: bool = False
_mock_started: bool = False


@app.route("/swagger/api/swagger.json", methods=["GET"])
def get_swagger() -> str:
    return json.dumps(spec.to_dict())


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

    return Image.new("RGB", (1920, 1080), color="white")


def depth_image() -> Image.Image:

    return Image.new("I;16", (1920, 1080), color="white")


@app.route("/state/start", methods=["PUT"])
def put_start() -> Tuple[str, int]:
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
        global _kinect
        assert _kinect is None
        _kinect = KinectAzure()

    return "ok", 200


@app.route("/state/stop", methods=["PUT"])
@requires_started
def put_stop() -> Tuple[str, int]:
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
def get_started() -> Tuple[str, int]:
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
def get_image_color() -> Response:
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
        cache_timeout=0,
    )


@app.route("/color/parameters", methods=["GET"])
@requires_started
def get_color_camera_parameters() -> Tuple[str, int]:
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
def get_image_depth() -> Response:
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
                image/jpeg:
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

    return send_file(image_to_bytes_io(img, target_format="PNG"), mimetype="image/png", cache_timeout=0)


@app.route("/synchronized/image", methods=["GET"])
@requires_started
def get_image_both() -> Response:
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
        mem_zip, mimetype="application/zip", cache_timeout=0, as_attachment=True, attachment_filename="synchronized.zip"
    )


with app.test_request_context():
    spec.path(view=put_start)
    spec.path(view=put_stop)
    spec.path(view=get_started)
    spec.path(view=get_image_color)
    spec.path(view=get_color_camera_parameters)
    spec.path(view=get_image_both)
    spec.path(view=get_image_depth)

spec.components.schema(CameraParameters.__name__, schema=CameraParameters)


def main() -> None:

    parser = argparse.ArgumentParser(description=SERVICE_NAME)
    parser.add_argument("-s", "--swagger", action="store_true", default=False)
    parser.add_argument("-m", "--mock", action="store_true", default=False)
    args = parser.parse_args()

    if args.swagger:
        print(spec.to_yaml())
        return

    global _mock
    _mock = args.mock
    if _mock:
        logger.info("Starting as a mock!")

    SWAGGER_URL = "/swagger"

    swaggerui_blueprint = get_swaggerui_blueprint(
        SWAGGER_URL, "./api/swagger.json"  # Swagger UI static files will be mapped to '{SWAGGER_URL}/dist/'
    )

    # Register blueprint at URL
    app.register_blueprint(swaggerui_blueprint, url_prefix=SWAGGER_URL)

    app.run(host="0.0.0.0", port=port_from_url(URL))

    if _kinect:
        _kinect.cleanup()


if __name__ == "__main__":
    main()
