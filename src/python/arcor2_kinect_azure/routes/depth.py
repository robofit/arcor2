from flask import Blueprint, request, send_file
from PIL import Image

from arcor2.flask import RespT
from arcor2.image import image_to_bytes_io
from arcor2_kinect_azure import app, get_data
from arcor2_kinect_azure.routes import requires_started

blueprint = Blueprint("depth", __name__, url_prefix="/depth")


def depth_image() -> Image.Image:
    return Image.open(get_data("depth.png"))


@blueprint.route("/image", methods=["GET"])
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
            500:
              description: "Error types: **General**, **StartError**."
              content:
                application/json:
                  schema:
                    $ref: WebApiError
    """

    if app.MOCK:
        img = depth_image()
    else:
        assert app.KINECT is not None
        img = app.KINECT.depth_image(num_frames=int(request.args.get("num_frames", default=1)))

    return send_file(image_to_bytes_io(img, target_format="PNG"), mimetype="image/png", max_age=0)
