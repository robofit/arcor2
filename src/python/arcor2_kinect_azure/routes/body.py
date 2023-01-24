import json
import time

from flask import Blueprint, Response, request

from arcor2.flask import RespT
from arcor2_kinect_azure import app
from arcor2_kinect_azure.routes import requires_started

blueprint = Blueprint("body", __name__, url_prefix="/body")


@blueprint.route("/count", methods=["GET"])
@requires_started
def get_body_count() -> RespT:
    """Get body count
    ---
    get:
        description: Get body count
        tags:
           - Kinect Azure
        responses:
            200:
              description: Ok
              content:
                application/json:
                    schema:
                        type: integer
            500:
              description: "Error types: **General**, **StartError**."
              content:
                application/json:
                  schema:
                    $ref: WebApiError
    """
    kinect = app.KINECT
    assert kinect is not None

    bodies = kinect.get_bodies()
    count = 0 if bodies is None else bodies.shape[0]
    return Response(response=str(count))


@blueprint.route("/present", methods=["GET"])
@requires_started
def is_user_present() -> RespT:
    """Get body count
    ---
    get:
        description: Returns true is someone is present
        tags:
           - Kinect Azure
        parameters:
            - in: query
              name: wait
              schema:
                type: boolean
                default: false
        responses:
            200:
              description: Ok
              content:
                application/json:
                    schema:
                        type: integer
            500:
              description: "Error types: **General**, **StartError**."
              content:
                application/json:
                  schema:
                    $ref: WebApiError
    """
    kinect = app.KINECT
    assert kinect is not None

    wait = json.loads(request.args.get("wait", "false"))

    while True:
        bodies = kinect.get_bodies()
        is_present = False if bodies is None else bodies.shape[0] > 0
        if wait and not is_present:
            time.sleep(0.1)
            continue
        return Response(response=json.dumps(is_present))
