#!/usr/bin/env python3

import argparse
import json
import os
import threading
import time

from flask import Response, jsonify, request

from arcor2 import env, rest
from arcor2.data.common import Pose, Position
from arcor2.flask import RespT, create_app, run_app
from arcor2.helpers import port_from_url
from arcor2.logging import get_logger
from arcor2_cube_detector.cube_detector import Cube
from arcor2_cube_tracker import version
from arcor2_cube_tracker.cube_tracker import CubeTracker, DistanceType
from arcor2_cube_tracker.exceptions import CubeTrackerGeneral, WebApiError

logger = get_logger(__name__)

URL = os.getenv("ARCOR2_CUBE_TRACKER_URL", "http://0.0.0.0:5021")
URL_DETECTOR = os.getenv("ARCOR2_CUBE_DETECTOR_URL", "http://0.0.0.0:5020")
SERVICE_NAME = "Cube Tracker Web API"

DETECTION_INTERVAL = env.get_float("ARCOR2_CUBE_TRACKER_INTERVAL", 1.0)

app = create_app(__name__)

_started = False
_mock = False
_tracker = CubeTracker(average_position=env.get_bool("ARCOR2_CUBE_TRACKER_AVERAGE_POSITION", True))
_thread: None | threading.Thread = None


def thread_detect_cubes() -> None:
    while _started:
        t_start = time.monotonic()
        try:
            cubes = rest.call(rest.Method.GET, f"{URL_DETECTOR}/detect/all", list_return_type=Cube)
            _tracker.store_cubes(cubes)
        except Exception:
            logger.warning("ERROR WHILE STORING CUBES")
        t_total = time.monotonic() - t_start

        if t_total > DETECTION_INTERVAL:
            logger.warning(f"Detection took longer than given interval ({t_total:.3f} > {DETECTION_INTERVAL})")
        else:
            time.sleep(DETECTION_INTERVAL - t_total)


@app.route("/state/start", methods=["PUT"])
def put_start() -> RespT:
    """Periodically call Object detector.
    ---
    put:
        description: Start.
        tags:
           - State
        responses:
            204:
              description: Ok
            500:
              description: "Error types: **General**"
              content:
                application/json:
                  schema:
                    $ref: WebApiError
    """
    # Remove every stored
    _tracker.stored_cubes = []

    global _started, _thread
    if not _mock and not _started:
        _started = True
        _thread = threading.Thread(target=thread_detect_cubes, args=())
        _thread.start()

    return Response(status=204)


@app.route("/state/stop", methods=["PUT"])
def put_stop() -> RespT:
    """Stop detecting.
    ---
    put:
        description: Stop.
        tags:
           - State
        responses:
            204:
              description: Ok
            500:
              description: "Error types: **General**"
              content:
                application/json:
                  schema:
                    $ref: WebApiError
    """

    global _started, _thread
    _started = False
    if _thread and _thread.is_alive():
        _thread.join()
    return Response(status=204)


@app.route("/state/started", methods=["GET"])
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
              description: "Error types: **General**"
              content:
                application/json:
                  schema:
                    $ref: WebApiError
    """

    global _started
    return jsonify(_started), 200


@app.route("/cubes/all", methods=["GET"])
def get_cubes() -> RespT:
    """Get cubes.
    ---
    get:
        description: Get all cubes.
        tags:
           - Cubes (All)
        parameters:
            - in: query
              name: color
              schema:
                type: string
                enum:
                    - RED
                    - GREEN
                    - BLUE
                    - YELLOW
              description: Color of the cube
        responses:
            200:
              description: Ok
              content:
                application/json:
                    schema:
                        type: array
                        items:
                            $ref: Pose
            500:
              description: "Error types: **General**"
              content:
                application/json:
                  schema:
                    $ref: WebApiError
    """
    color = request.args.get("color", default=None)
    return jsonify(_tracker.get_stored_cubes(color)), 200


@app.route("/cube/is-in-area", methods=["PUT"])
def is_cube_in_area() -> RespT:
    """Get cubes.
    ---
    put:
        description: Check if cube is in the area
        tags:
           - Cube (Distance)
        requestBody:
          content:
            application/json:
              schema:
                $ref: Position
        parameters:
            - in: query
              name: max_distance
              schema:
                type: number
                default: 1.0
                format: float
                minimum: 0.0
              description: Maximum distance from the point of interest
            - in: query
              name: color
              schema:
                type: string
                enum:
                    - RED
                    - GREEN
                    - BLUE
                    - YELLOW
              description: Color of the cube
        responses:
            200:
              description: Ok
              content:
                application/json:
                    schema:
                      type: boolean
            500:
              description: "Error types: **General**, **CubeTrackerGeneral**"
              content:
                application/json:
                  schema:
                    $ref: WebApiError
    """
    if not isinstance(request.json, dict):
        raise CubeTrackerGeneral("Body should be a JSON dict containing Position.")
    position = Position.from_dict(request.json)
    max_distance = float(request.args.get("max_distance", default=1))
    color = request.args.get("color", default=None)
    if color == "ANY":
        color = None

    cube = _tracker.get_cube_by_distance(
        DistanceType.NEAREST,
        position,
        Position(0, 0, 0),
        max_distance,
        color,
    )
    return Response(json.dumps(cube is not None))


@app.route("/cube/nearest", methods=["PUT"])
def get_cubes_nearest() -> RespT:
    """Get cubes.
    ---
    put:
        description: Get the nearest cube.
        tags:
           - Cube (Distance)
        requestBody:
          content:
            application/json:
              schema:
                $ref: Position
        parameters:
            - in: query
              name: max_distance
              schema:
                type: number
                default: 1.0
                format: float
                minimum: 0.0
              description: Maximum distance from the point of interest
            - in: query
              name: color
              schema:
                type: string
                enum:
                    - RED
                    - GREEN
                    - BLUE
                    - YELLOW
              description: Color of the cube
            - in: query
              name: offset_x
              schema:
                type: number
                default: 0.0
                format: float
              description: Offset from the cube center on x axis
            - in: query
              name: offset_y
              schema:
                type: number
                default: 0.0
                format: float
              description: Offset from the cube center on y axis
            - in: query
              name: offset_z
              schema:
                type: number
                default: 0.0
                format: float
              description: Offset from the cube center on z axis
        responses:
            200:
              description: Ok
              content:
                application/json:
                    schema:
                      $ref: Pose
            500:
              description: "Error types: **General**, **CubeTrackerGeneral**"
              content:
                application/json:
                  schema:
                    $ref: WebApiError
    """
    if not isinstance(request.json, dict):
        raise CubeTrackerGeneral("Body should be a JSON dict containing Position.")
    position = Position.from_dict(request.json)
    max_distance = float(request.args.get("max_distance", default=1))
    color = request.args.get("color", default=None)
    if color == "ANY":
        color = None
    offset = Position(
        float(request.args.get("offset_x", default=0)),
        float(request.args.get("offset_y", default=0)),
        float(request.args.get("offset_z", default=0)),
    )
    return (
        jsonify(
            _tracker.get_cube_by_distance(
                DistanceType.NEAREST,
                position,
                offset,
                max_distance,
                color,
            )
        ),
        200,
    )


@app.route("/cube/farthest", methods=["PUT"])
def get_cubes_farthest() -> RespT:
    """Get cubes.
    ---
    put:
        description: Get the farthest cube.
        tags:
           - Cube (Distance)
        requestBody:
          content:
            application/json:
              schema:
                $ref: Position
        parameters:
            - in: query
              name: max_distance
              schema:
                type: number
                default: 1.0
                format: float
                minimum: 0.0
              description: Maximum distance from the point of interest
            - in: query
              name: color
              schema:
                type: string
                enum:
                    - RED
                    - GREEN
                    - BLUE
                    - YELLOW
              description: Color of the cube
            - in: query
              name: offset_x
              schema:
                type: number
                default: 0.0
                format: float
              description: Offset from the cube center on x axis
            - in: query
              name: offset_y
              schema:
                type: number
                default: 0.0
                format: float
              description: Offset from the cube center on y axis
            - in: query
              name: offset_z
              schema:
                type: number
                default: 0.0
                format: float
              description: Offset from the cube center on z axis
        responses:
            200:
              description: Ok
              content:
                application/json:
                    schema:
                      $ref: Pose
            500:
              description: "Error types: **General**, **CubeTrackerGeneral**"
              content:
                application/json:
                  schema:
                    $ref: WebApiError
    """
    if not isinstance(request.json, dict):
        raise CubeTrackerGeneral("Body should be a JSON dict containing Position.")
    position = Position.from_dict(request.json)
    max_distance = float(request.args.get("max_distance", default=1))
    color = request.args.get("color", default=None)
    if color == "ANY":
        color = None
    offset = Position(
        float(request.args.get("offset_x", default=0)),
        float(request.args.get("offset_y", default=0)),
        float(request.args.get("offset_z", default=0)),
    )
    return (
        jsonify(_tracker.get_cube_by_distance(DistanceType.FARTHEST, position, offset, max_distance, color)),
        200,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=SERVICE_NAME)
    parser.add_argument("-s", "--swagger", action="store_true", default=False)
    parser.add_argument("-m", "--mock", action="store_true", default=env.get_bool("ARCOR2_CUBE_TRACKER_MOCK"))
    args = parser.parse_args()

    global _mock
    _mock = args.mock
    if _mock:
        logger.info("Starting as a mock!")

    run_app(app, SERVICE_NAME, version(), port_from_url(URL), [WebApiError, Pose], args.swagger)


if __name__ == "__main__":
    main()
