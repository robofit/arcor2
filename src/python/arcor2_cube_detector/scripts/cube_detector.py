#!/usr/bin/env python3

import argparse
import io
import os
import zipfile

from flask import jsonify

from arcor2 import env, rest
from arcor2.data.camera import CameraParameters
from arcor2.data.common import Pose, Position
from arcor2.exceptions import Arcor2Exception
from arcor2.flask import RespT, create_app, run_app
from arcor2.helpers import port_from_url
from arcor2.logging import get_logger
from arcor2_cube_detector import version
from arcor2_cube_detector.cube_detector import Color, Cube, CubeDetector
from arcor2_cube_detector.exceptions import DetectorNotStarted, WebApiError

logger = get_logger(__name__)

URL = os.getenv("ARCOR2_CUBE_DETECTOR_URL", "http://0.0.0.0:5020")
URL_KINECT = os.getenv("ARCOR2_KINECT_AZURE_URL", "http://0.0.0.0:5016")
SERVICE_NAME = "Cube Detector Web API"

app = create_app(__name__)

_detector: CubeDetector | None = None
_mock: bool = False


@app.route("/detect/all", methods=["GET"])
def detect_all() -> RespT:
    """Detect cubes
    ---
    get:
        description: Detects cubes in image.
        tags:
           - Synchronized
        responses:
            200:
              description: Ok
              content:
                application/json:
                    schema:
                        type: array
                        items:
                            $ref: Cube
            500:
              description: "Error types: **General**, **KinectNotStarted**."
              content:
                application/json:
                  schema:
                    $ref: WebApiError
    """
    if not _mock:
        global _detector

        try:
            kinect_started = rest.call(rest.Method.GET, f"{URL_KINECT}/state/started", return_type=bool)
        except Arcor2Exception as e:
            raise DetectorNotStarted("Detector is not started") from e
        if not kinect_started:
            raise DetectorNotStarted("Detector is not started")

        if _detector is None:
            image = rest.get_image(f"{URL_KINECT}/color/image")
            parameters = rest.call(rest.Method.GET, f"{URL_KINECT}/color/parameters", return_type=CameraParameters)
            _detector = CubeDetector(parameters, image.width, image.height)

        synchronized = rest.call(rest.Method.GET, f"{URL_KINECT}/synchronized/image", return_type=io.BytesIO)
        with zipfile.ZipFile(synchronized, mode="r") as zip:
            color = zip.read("color.jpg")
            depth = zip.read("depth.png")
        color, depth = _detector.get_image_from_bytes(color, depth)
        detected_cubes = _detector.detect_cubes(color, depth)
    else:
        detected_cubes = [Cube(Color.RED.name, Pose(Position(0, 0, 0))), Cube(Color.BLUE.name, Pose(Position(1, 1, 1)))]

    return jsonify(detected_cubes), 200


def main() -> None:
    parser = argparse.ArgumentParser(description=SERVICE_NAME)
    parser.add_argument("-s", "--swagger", action="store_true", default=False)
    parser.add_argument("-m", "--mock", action="store_true", default=env.get_bool("ARCOR2_CUBE_DETECTOR_MOCK"))
    args = parser.parse_args()

    global _mock
    _mock = args.mock
    if _mock:
        logger.info("Starting as a mock!")

    run_app(app, SERVICE_NAME, version(), port_from_url(URL), [WebApiError, Cube], args.swagger)


if __name__ == "__main__":
    main()
