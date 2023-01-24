import argparse
import os
from typing import TYPE_CHECKING

from arcor2 import env
from arcor2.data.camera import CameraParameters
from arcor2.data.common import Pose, Position
from arcor2.flask import create_app, run_app
from arcor2.helpers import port_from_url
from arcor2.logging import get_logger
from arcor2_kinect_azure import ARCOR2_KINECT_AZURE_LOG_LEVEL, version
from arcor2_kinect_azure.exceptions import WebApiError
from arcor2_kinect_azure.routes import (
    aggregation,
    body,
    color,
    debug_request,
    depth,
    position,
    skeleton,
    state,
    synchronized,
    video,
)

logger = get_logger(__name__, ARCOR2_KINECT_AZURE_LOG_LEVEL)

URL = os.getenv("ARCOR2_KINECT_AZURE_URL", "http://localhost:5016")
SERVICE_NAME = "Kinect Azure Web API"

app = create_app(__name__)

if TYPE_CHECKING:
    from arcor2_kinect_azure.kinect import KinectAzure

KINECT: "None | KinectAzure" = None
MOCK: bool = False
MOCK_STARTED: bool = False

POSITION: Position = Position()


def main() -> None:
    parser = argparse.ArgumentParser(description=SERVICE_NAME)
    parser.add_argument("-s", "--swagger", action="store_true", default=False)
    parser.add_argument("-m", "--mock", action="store_true", default=env.get_bool("ARCOR2_KINECT_AZURE_MOCK"))
    args = parser.parse_args()

    global MOCK
    MOCK = args.mock
    if MOCK:
        logger.info("Starting as a mock!")

    app.register_blueprint(aggregation.blueprint)
    app.register_blueprint(body.blueprint)
    app.register_blueprint(color.blueprint)
    app.register_blueprint(depth.blueprint)
    app.register_blueprint(position.blueprint)
    app.register_blueprint(skeleton.blueprint)
    app.register_blueprint(state.blueprint)
    app.register_blueprint(synchronized.blueprint)
    app.register_blueprint(video.blueprint)
    app.before_request(debug_request)
    run_app(app, SERVICE_NAME, version(), port_from_url(URL), [CameraParameters, WebApiError, Pose], args.swagger)

    if KINECT is not None:
        KINECT.cleanup()
