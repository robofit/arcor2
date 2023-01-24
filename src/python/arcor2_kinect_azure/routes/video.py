from flask import Blueprint, Response, render_template_string

from arcor2.flask import RespT
from arcor2_kinect_azure import app
from arcor2_kinect_azure.routes import requires_started

blueprint = Blueprint("video", __name__, url_prefix="/video")


@blueprint.route("/show", methods=["GET"])
@requires_started
def show() -> RespT:
    """Show live feed from the camera in browser
    ---
    get:
        description: Show live feed from camera in browser
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
    assert app.KINECT

    return (
        render_template_string(
            """
        <!DOCTYPE html>
        <html>
        <body>
        <h1>Live streaming</h1>
        <div>
            <img src="{{ url_for('video.get_feed') }}" width="100%"/>
        </div>
        </body>
        </html>
        """
        ),
        200,
    )


@blueprint.route("/get-feed", methods=["GET"])
@requires_started
def get_feed() -> RespT:
    assert app.KINECT

    return Response(app.KINECT.get_video_feed(), mimetype="multipart/x-mixed-replace; boundary=frame")
