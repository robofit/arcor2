from flask import Blueprint, send_file

from arcor2.flask import RespT
from arcor2.image import image_to_bytes_io
from arcor2_kinect_azure import app
from arcor2_kinect_azure.routes import requires_started
from arcor2_kinect_azure.routes.color import color_image

blueprint = Blueprint("skeleton", __name__, url_prefix="/skeleton")


@blueprint.route("/image", methods=["GET"])
@requires_started
def get_skeleton_image() -> RespT:
    """Get the color image with visualized skeleton.
    ---
    get:
        description: Get the color image with visualized skeleton.
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
        img = app.KINECT.skeleton_image()

    return send_file(
        image_to_bytes_io(img, target_format="JPEG", target_mode="RGB"),
        mimetype="image/jpeg",
        max_age=0,
    )
