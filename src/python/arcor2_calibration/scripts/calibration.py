#!/usr/bin/env python3

import argparse
import logging
import math
import random
import sys
import time

import numpy as np
import quaternion
import yaml
from dataclasses_jsonschema import ValidationError
from flask import jsonify, request
from PIL import Image

import arcor2_calibration
from arcor2 import env
from arcor2 import transformations as tr
from arcor2.data.common import Pose, Position
from arcor2.flask import RespT, create_app, run_app
from arcor2.helpers import port_from_url
from arcor2.logging import get_logger
from arcor2.urdf import urdf_from_url
from arcor2_calibration import calibration
from arcor2_calibration.calibration import detect_corners, estimate_camera_pose
from arcor2_calibration.quaternions import weighted_average_quaternions
from arcor2_calibration.robot import calibrate_robot
from arcor2_calibration_data import CALIBRATION_URL, SERVICE_NAME, Corner, EstimatedPose, MarkerCorners
from arcor2_calibration_data.client import CalibrateRobotArgs
from arcor2_calibration_data.exceptions import Invalid, NotFound, WebApiError

logger = get_logger(__name__)
logger.propagate = False

MARKERS: dict[int, Pose] = {}
MARKER_SIZE = 0.1

MIN_DIST = 0.3
MAX_DIST = 2.0

MIN_THETA = 2.0
MAX_THETA = math.pi

_mock: bool = False

app = create_app(__name__)


def camera_matrix_from_request() -> list[list[float]]:

    return [
        [float(request.args["fx"]), 0.00000, float(request.args["cx"])],
        [0.00000, float(request.args["fy"]), float(request.args["cy"])],
        [0.00000, 0.00000, 1],
    ]


def dist_matrix_from_request() -> list[float]:
    return [float(val) for val in request.args.getlist("distCoefs")]


def normalize(val: float, min_val: float, max_val: float) -> float:

    assert max_val > min_val
    res = (min(max(abs(val), min_val), max_val) - min_val) / (max_val - min_val)
    assert 0 <= res <= 1
    return res


@app.route("/calibrate/robot", methods=["PUT"])
def put_calibrate_robot() -> RespT:
    """Get calibration (camera pose wrt. marker)
    ---
    put:
        description: Get calibration
        tags:
           - Robot
        requestBody:
              content:
                multipart/form-data:
                  schema:
                    type: object
                    required:
                        - image
                        - args
                    properties:
                      # 'image' will be the field name in this multipart request
                      image:
                        type: string
                        format: binary
                      args:
                        $ref: "#/components/schemas/CalibrateRobotArgs"
        responses:
            200:
              description: Ok
              content:
                application/json:
                  schema:
                    $ref: Pose
            500:
              description: "Error types: **General**."
              content:
                    application/json:
                      schema:
                        $ref: WebApiError

    """

    image = Image.open(request.files["image"].stream)
    args = CalibrateRobotArgs.from_json(request.files["args"].stream.read().decode())

    if _mock:
        time.sleep(5)
        pose = args.robot_pose
        pose.position.x += random.uniform(-0.1, 0.1)
        pose.position.y += random.uniform(-0.1, 0.1)
        pose.position.z += random.uniform(-0.1, 0.1)
    else:
        pose = calibrate_robot(
            args.robot_joints,
            args.robot_pose,
            args.camera_pose,
            args.camera_parameters,
            urdf_from_url(args.urdf_uri),
            image,
        )

    return jsonify(pose.to_dict()), 200


@app.route("/markers/corners", methods=["PUT"])
def get_marker_corners() -> RespT:
    """Detect marker corners.
    ---
    put:
        description: Detect marker corners
        tags:
           - Camera
        parameters:
            - in: query
              name: fx
              schema:
                type: number
                format: float
              required: true
              description: unique ID
            - in: query
              name: fy
              schema:
                type: number
                format: float
              required: true
              description: unique ID
            - in: query
              name: cx
              schema:
                type: number
                format: float
              required: true
              description: unique ID
            - in: query
              name: cy
              schema:
                type: number
                format: float
              required: true
              description: unique ID
            - in: query
              name: distCoefs
              schema:
                type: array
                items:
                    type: number
                    format: float
              required: true
              description: unique ID
        requestBody:
              content:
                multipart/form-data:
                  schema:
                    type: object
                    required:
                        - image
                    properties:
                      # 'image' will be the field name in this multipart request
                      image:
                        type: string
                        format: binary
        responses:
            200:
              description: Ok
              content:
                application/json:
                  schema:
                    type: array
                    items:
                        $ref: MarkerCorners
            500:
              description: "Error types: **General**."
              content:
                    application/json:
                      schema:
                        $ref: WebApiError

    """

    file = request.files["image"]
    camera_matrix = camera_matrix_from_request()
    image = Image.open(file.stream)
    dist_matrix = dist_matrix_from_request()

    corners: list[MarkerCorners] = []

    if _mock:
        time.sleep(0.1)
        corners = [MarkerCorners(10, [Corner(934, 831), Corner(900, 1007), Corner(663, 999), Corner(741, 828)])]
    else:
        _, _, _, detected_corners, ids = detect_corners(camera_matrix, dist_matrix, image)

        for mid, corn in zip(ids, detected_corners[0]):
            corners.append(MarkerCorners(int(mid), [Corner(float(v[0]), float(v[1])) for v in corn]))

    return jsonify(corners), 200


@app.route("/calibrate/camera", methods=["PUT"])
def get_calibration() -> RespT:
    """Get calibration (camera pose wrt. marker)
    ---
    put:
        description: Returns camera pose with respect to the origin.
        tags:
           - Camera
        parameters:
            - in: query
              name: inverse
              schema:
                type: boolean
              description: When set, the method returns pose of the origin wrt. the camera.
            - in: query
              name: fx
              schema:
                type: number
                format: float
              required: true
              description: unique ID
            - in: query
              name: fy
              schema:
                type: number
                format: float
              required: true
              description: unique ID
            - in: query
              name: cx
              schema:
                type: number
                format: float
              required: true
              description: unique ID
            - in: query
              name: cy
              schema:
                type: number
                format: float
              required: true
              description: unique ID
            - in: query
              name: distCoefs
              schema:
                type: array
                items:
                    type: number
                    format: float
              required: true
              description: unique ID
        requestBody:
              content:
                multipart/form-data:
                  schema:
                    type: object
                    required:
                        - image
                    properties:
                      # 'image' will be the field name in this multipart request
                      image:
                        type: string
                        format: binary
        responses:
            200:
              description: Ok
              content:
                application/json:
                  schema:
                    $ref: EstimatedPose
            500:
              description: "Error types: **General**, **NotFound**, **Invalid**."
              content:
                    application/json:
                      schema:
                        $ref: WebApiError
    """

    file = request.files["image"]

    camera_matrix = camera_matrix_from_request()
    image = Image.open(file.stream)
    dist_matrix = dist_matrix_from_request()

    if _mock:
        time.sleep(0.5)
        quality = random.uniform(0, 1)
        pose = Pose(Position(random.uniform(-0.5, 0.5), random.uniform(-0.5, 0.5), random.uniform(0.2, 1)))
    else:
        poses = estimate_camera_pose(camera_matrix, dist_matrix, image, MARKER_SIZE)

        if not poses:
            raise NotFound("No marker detected.")

        quality_dict: dict[int, float] = {k: 0.0 for k, v in MARKERS.items()}
        known_markers: list[tuple[Pose, float]] = []

        # apply configured marker offset from origin to the detected poses
        for marker_id in poses.keys():
            try:
                cpose = MARKERS[marker_id]
            except KeyError:
                logger.debug(f"Detected un-configured marker id {marker_id}.")
                continue

            mpose = poses[marker_id]
            dist = math.sqrt(mpose.position.x**2 + mpose.position.y**2 + mpose.position.z**2)

            # the closer the theta is to pi, the higher quality we get
            theta = quaternion.as_spherical_coords(mpose.orientation.as_quaternion())[0]
            ori_marker_quality = normalize(abs(theta), MIN_THETA, MAX_THETA)

            # the closer the marker is, the higher quality we get
            dist_marker_quality = 1.0 - normalize(dist, MIN_DIST, MAX_DIST)

            marker_quality = (ori_marker_quality + dist_marker_quality) / 2

            quality_dict[marker_id] = marker_quality
            known_markers.append((tr.make_pose_abs(cpose, mpose), marker_quality))

            logger.debug(f"Known marker       : {marker_id}")
            logger.debug(f"...original pose   : {poses[marker_id]}")
            logger.debug(f"...transformed pose: {poses[marker_id]}")
            logger.debug(f"...dist quality    : {dist_marker_quality:.3f}")
            logger.debug(f"...ori quality     : {ori_marker_quality:.3f}")
            logger.debug(f"...overall quality : {marker_quality:.3f}")

        if not known_markers:
            raise NotFound("No known marker detected.")

        weights = [marker[1] for marker in known_markers]
        wsum = sum(weights)

        if wsum <= 0:
            logger.warning(
                f"Got invalid weights, probably bad input data.\n"
                f"Camera matrix: {camera_matrix}\n"
                f"Dist matrix: {dist_matrix}"
            )
            raise Invalid("Invalid input data.")

        # combine all detections
        pose = Pose()
        for mpose, weight in known_markers:
            pose.position += mpose.position * weight
        pose.position *= 1.0 / wsum

        quaternions = np.array([quaternion.as_float_array(km[0].orientation.as_quaternion()) for km in known_markers])
        pose.orientation.set_from_quaternion(
            quaternion.from_float_array(weighted_average_quaternions(quaternions, np.array(weights)))
        )

        quality = float(np.mean(list(quality_dict.values())))

    inverse = request.args.get("inverse", default="false") == "true"

    if inverse:
        logger.debug("Inverting the output pose.")
        pose = pose.inversed()

    return jsonify(EstimatedPose(pose, quality)), 200


def main() -> None:

    parser = argparse.ArgumentParser(description=SERVICE_NAME)

    parser.add_argument(
        "-d",
        "--debug",
        help="Set logging level to debug.",
        action="store_const",
        const=logging.DEBUG,
        default=logging.DEBUG if env.get_bool("ARCOR2_CALIBRATION_DEBUG") else logging.INFO,
    )

    run_as_mock = env.get_bool("ARCOR2_CALIBRATION_MOCK")

    # argparse has not support for env vars so this is kind of workaround
    # TODO maybe it could be solved using a custom action like https://gist.github.com/orls/51525c86ee77a56ad396
    if not run_as_mock:

        group = parser.add_mutually_exclusive_group(required=True)

        group.add_argument(
            "--config-file",
            "-c",
            type=argparse.FileType("r"),
            help="Config file name containing a valid YAML configuration.",
        )

        sub_group = group.add_mutually_exclusive_group()
        sub_group.add_argument("-s", "--swagger", action="store_true", default=False)
        sub_group.add_argument(
            "-m",
            "--mock",
            action="store_true",
            default=False,
            help="Run the service in a mock mode. The same can be done by setting ARCOR2_CALIBRATION_MOCK.",
        )

    args = parser.parse_args()

    logger.setLevel(args.debug)

    if not (run_as_mock or args.swagger or args.mock):

        data = args.config_file.read()

        global MARKER_SIZE
        global MIN_DIST
        global MAX_DIST

        try:

            config = yaml.safe_load(data)

            MARKER_SIZE = float(config.get("marker_size", MARKER_SIZE))
            MIN_DIST = float(config.get("min_dist", MIN_DIST))
            MAX_DIST = float(config.get("max_dist", MAX_DIST))
            calibration.BLUR_THRESHOLD = float(config.get("blur_threshold", calibration.BLUR_THRESHOLD))

            for marker_id, marker in config["markers"].items():
                MARKERS[int(marker_id)] = Pose.from_dict(marker["pose"])

            logger.info(
                f"Loaded configuration id '{config['id']}' with {len(MARKERS)} marker(s) of size {MARKER_SIZE}."
            )

        except (KeyError, ValueError, TypeError, ValidationError):
            logger.exception("Failed to load the configuration file.")
            sys.exit(1)

    if not (MAX_DIST > MIN_DIST):
        logger.error("'max_dist' have to be bigger than 'min_dist'.")
        sys.exit(1)

    global _mock
    _mock = run_as_mock or args.mock
    if _mock:
        logger.info("Starting as a mock!")

    run_app(
        app,
        SERVICE_NAME,
        arcor2_calibration.version(),
        port_from_url(CALIBRATION_URL),
        [Pose, CalibrateRobotArgs, MarkerCorners, EstimatedPose, WebApiError],
        getattr(args, "swagger", False),
    )


if __name__ == "__main__":
    main()
