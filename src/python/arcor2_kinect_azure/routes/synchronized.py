import io
import zipfile

from flask import Blueprint, send_file

from arcor2.flask import RespT
from arcor2.image import image_to_bytes_io
from arcor2_kinect_azure import app
from arcor2_kinect_azure.routes import requires_started
from arcor2_kinect_azure.routes.color import color_image
from arcor2_kinect_azure.routes.depth import depth_image

blueprint = Blueprint("synchronized", __name__, url_prefix="/synchronized")


@blueprint.route("/synchronized/image", methods=["GET"])
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
            500:
              description: "Error types: **General**, **StartError**."
              content:
                application/json:
                  schema:
                    $ref: WebApiError
    """

    if app.MOCK:
        color = color_image()
        depth = depth_image()
    else:
        assert app.KINECT is not None
        both = app.KINECT.sync_images()
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
