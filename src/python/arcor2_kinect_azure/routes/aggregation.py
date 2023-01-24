import json
from http import HTTPStatus

from flask import Blueprint, Response, request

from arcor2.data.common import BodyJointId
from arcor2.logging import get_logger
from arcor2_kinect_azure import ARCOR2_KINECT_AZURE_LOG_LEVEL, app
from arcor2_kinect_azure.kinect.aggregation import DirectionWithSpeed, FailedToComputeError, Moving
from arcor2_kinect_azure.routes import requires_started

log = get_logger(__name__, ARCOR2_KINECT_AZURE_LOG_LEVEL)

blueprint = Blueprint("aggregation", __name__, url_prefix="/aggregation")


@blueprint.route("/is-moving", methods=["GET"])
@requires_started
def is_moving() -> Response:
    """See if a body part is moving in certain direction at certain speed
    ---
    get:
        description: Get true if body part is moving
        tags:
           - Kinect Azure
        parameters:
            - in: query
              name: body_id
              schema:
                type: integer
                default: 0
            - in: query
              name: joint_id
              schema:
                type: integer
                default: 2
                minimum: 0
                maximum: 31
            - in: query
              name: num_samples
              schema:
                type: integer
                default: 5
            - in: query
              name: best_effort
              schema:
                type: boolean
                default: false
            - in: query
              name: speed
              description: Minimum speed
              schema:
                type: number
                format: float
                default: 0.1
                minimum: 0.0
            - in: query
              name: deviation
              description: How precise should the measurement be
              schema:
                type: number
                format: float
                default: 0.1
                minimum: 0.0
                maximum: 1.0
        requestBody:
              content:
                application/json:
                  schema:
                    $ref: Orientation
        responses:
            200:
              description: Ok
              content:
                application/json:
                    schema:
                        type: boolean
            500:
              description: "Error types: **General**, **StartError**."
              content:
                application/json:
                  schema:
                    $ref: WebApiError
    """
    body_id = int(request.args.get("body_id") or 0)
    joint_id = BodyJointId.from_str_or_default(request.args.get("joint_id"))
    num_samples = int(request.args.get("num_samples") or 5)
    deviation = float(request.args.get("deviation") or 0.1)
    if not (1 < num_samples < 30):
        return Response(
            response='"Wrong number of samples provided"',
            status=HTTPStatus.FORBIDDEN,
        )
    best_effort = bool(request.args.get("best_effort") or False)
    if best_effort:
        log.debug(f'"Computing with {best_effort=}"')
    try:
        direction_w_speed = DirectionWithSpeed.from_request(request)
    except (TypeError, ValueError) as e:
        log.exception(e)
        return Response(response='"Cannot build DirectionWitSpeed from request"', status=HTTPStatus.FORBIDDEN)

    assert app.KINECT is not None
    buffer = app.KINECT.get_n_non_empty_captures(num_samples)
    if buffer is None:
        return Response('"No user in frame"', status=HTTPStatus.INTERNAL_SERVER_ERROR)

    moving_direction = Moving(
        compute_buffer=buffer,
        body_index=body_id,
        joint_index=joint_id,
        num_samples=num_samples,
        best_effort=best_effort,
        camera_fps=app.KINECT.config().camera_fps,
    )

    try:
        moving_direction.compute()
    except FailedToComputeError:
        return Response(response='"Failed to compute speed"', status=HTTPStatus.INTERNAL_SERVER_ERROR)

    moving_direction_w_speed = DirectionWithSpeed.from_moving(moving_direction)
    if moving_direction_w_speed.is_zero():
        is_faster = False
    else:
        is_faster = moving_direction_w_speed.is_faster_than(direction_w_speed, deviation)

    return Response(response=json.dumps(is_faster))
