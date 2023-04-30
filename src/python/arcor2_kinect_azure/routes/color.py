from flask import Blueprint, jsonify, send_file
from PIL import Image

from arcor2.data.camera import CameraParameters
from arcor2.flask import RespT
from arcor2.image import image_to_bytes_io
from arcor2_kinect_azure import app, get_data
from arcor2_kinect_azure.exceptions import StartError
from arcor2_kinect_azure.routes import requires_started

blueprint = Blueprint("color", __name__, url_prefix="/color")


def color_image() -> Image.Image:
    return Image.open(get_data("rgb.jpg"))


@blueprint.route("/image", methods=["GET"])
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
            500:
              description: "Error types: **General**, **StartError**."
              content:
                application/json:
                  schema:
                    $ref: WebApiError
    """

    if app.MOCK:
        img = color_image()
    else:
        assert app.KINECT is not None
        img = app.KINECT.color_image()

    return send_file(
        image_to_bytes_io(img, target_format="JPEG", target_mode="RGB"),
        mimetype="image/jpeg",
        max_age=0,
    )


@blueprint.route("/parameters", methods=["GET"])
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
            500:
              description: "Error types: **General**, **StartError**."
              content:
                application/json:
                  schema:
                    $ref: WebApiError
    """

    if app.MOCK:
        params = CameraParameters(
            915.575, 915.425, 957.69, 556.35, [0.447, -2.5, 0.00094, -0.00053, 1.432, 0.329, -2.332, 1.363]
        )
    else:
        assert app.KINECT is not None

        if not app.KINECT.color_camera_params:
            raise StartError("Failed to get camera parameters")

        params = app.KINECT.color_camera_params

    return jsonify(params.to_dict()), 200
