import json
from http import HTTPStatus

from flask import Blueprint, Response, request

from arcor2.data.common import Pose
from arcor2.flask import RespT
from arcor2.logging import get_logger
from arcor2_kinect_azure import ARCOR2_KINECT_AZURE_LOG_LEVEL, app
from arcor2_kinect_azure.exceptions import StartError
from arcor2_kinect_azure.routes import requires_started, started

log = get_logger(__name__, ARCOR2_KINECT_AZURE_LOG_LEVEL)

blueprint = Blueprint("state", __name__, url_prefix="/state")


@blueprint.route("/start", methods=["PUT"])
def put_start() -> RespT:
    """Start the sensor.
    ---
    put:
        description: Start the robot.
        tags:
           - State
        requestBody:
              content:
                application/json:
                  schema:
                    $ref: Pose
        responses:
            204:
              description: Ok
            500:
              description: "Error types: **General**, **DobotGeneral**, **StartError**."
              content:
                application/json:
                  schema:
                    $ref: WebApiError
    """

    if started():
        raise StartError("Already started.")

    if app.MOCK:
        app.MOCK_STARTED = True
    else:
        if not isinstance(request.json, dict):
            StartError("Body should be a JSON dict containing Pose.")
        camera_pose = Pose.from_json(request.data)

        # lazy import so mock mode can work without pyk4a installed
        from arcor2_kinect_azure.kinect import KinectAzure

        assert app.KINECT is None
        app.KINECT = KinectAzure()

        app.KINECT.set_camera_pose(camera_pose)

    log.info("Started")
    return Response(response="ok", status=HTTPStatus.OK)


@blueprint.route("/full-start", methods=["PUT"])
def put_full_start() -> RespT:
    """Start the sensor.
    ---
    put:
        description: Start the sensor and start capturing all frames.
        tags:
           - State
        requestBody:
              content:
                application/json:
                  schema:
                    $ref: Pose
        responses:
            200:
              description: Ok
            405:
              description: Already running
            500:
              description: "Error types: **General**, **StartError**."
              content:
                application/json:
                  schema:
                    $ref: WebApiError
    """
    if started():
        return Response(response="Already running.", status=HTTPStatus.METHOD_NOT_ALLOWED)

    if app.MOCK:
        app.MOCK_STARTED = True
    else:
        if not isinstance(request.json, dict):
            StartError("Body should be a JSON dict containing Pose.")
        camera_pose = Pose.from_json(request.data)

        # lazy import so mock mode can work without pyk4a installed
        from arcor2_kinect_azure.kinect import KinectAzure

        assert app.KINECT is None
        app.KINECT = KinectAzure()

        app.KINECT.set_camera_pose(camera_pose)

        app.KINECT.start_capturing()

    log.info("Started and capturing")
    return Response(response="ok", status=HTTPStatus.OK)


@blueprint.route("/start-capturing", methods=["PUT"])
@requires_started
def put_capture() -> RespT:
    """Start the capturing.
    ---
    put:
        description: Start capturing all frames.
        tags:
           - State
        responses:
            200:
              description: Ok
            500:
              description: "Error types: **General**, **StartError**."
              content:
                application/json:
                  schema:
                    $ref: WebApiError
    """

    if not app.MOCK:
        assert app.KINECT is not None
        app.KINECT.start_capturing()

    log.info("Capturing")
    return Response(response="ok", status=HTTPStatus.OK)


@blueprint.route("/stop", methods=["PUT"])
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
            500:
              description: "Error types: **General**, **StartError**."
              content:
                application/json:
                  schema:
                    $ref: WebApiError
    """

    if app.MOCK:
        app.MOCK_STARTED = False
    else:
        assert app.KINECT is not None
        app.KINECT.cleanup()
        app.KINECT = None
    log.info("Stopped")
    return Response(response="ok", status=HTTPStatus.OK)


@blueprint.route("/started", methods=["GET"])
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
            500:
              description: "Error types: **General**, **StartError**."
              content:
                application/json:
                  schema:
                    $ref: WebApiError
    """
    return Response(response=json.dumps(started()), status=HTTPStatus.OK)


@blueprint.route("/pose", methods=["GET"])
@requires_started
def get_pose() -> RespT:
    """Returns the pose configured during startup.
    ---
    get:
        description: Returns the pose configured during startup.
        tags:
           - State
        responses:
            200:
              description: Ok
              content:
                application/json:
                  schema:
                    $ref: Pose
            500:
              description: "Error types: **General**, **StartError**."
              content:
                application/json:
                  schema:
                    $ref: WebApiError
    """
    kinect = app.KINECT
    assert kinect is not None

    pose = kinect.get_camera_pose()

    return Response(response=pose.to_json(), status=HTTPStatus.OK)


@blueprint.route("/pose", methods=["PUT"])
@requires_started
def put_pose() -> RespT:
    """Sets sensor pose in runtime.
    ---
    put:
        description: Sets sensor pose in runtime.
        tags:
           - State
        requestBody:
          content:
            application/json:
              schema:
                $ref: Pose
        responses:
            204:
              description: Ok
            500:
              description: "Error types: **General**, **StartError**."
              content:
                application/json:
                  schema:
                    $ref: WebApiError
    """

    if not isinstance(request.json, dict):
        raise StartError("Body should be a JSON dict containing Pose.")

    kinect = app.KINECT
    assert kinect is not None

    pose = Pose.from_dict(request.json)

    kinect.set_camera_pose(pose)

    return Response(response="ok", status=HTTPStatus.OK)
