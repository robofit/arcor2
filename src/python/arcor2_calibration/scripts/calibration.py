#!/usr/bin/env python3

import argparse
import os
import random
import time

from arcor2_calibration_data import CALIBRATION_URL, SERVICE_NAME
from arcor2_calibration_data.client import CalibrateRobotArgs
from flask import jsonify, request
from PIL import Image

import arcor2_calibration
from arcor2.data.common import Pose, Position
from arcor2.flask import RespT, create_app, run_app
from arcor2.helpers import port_from_url
from arcor2.logging import get_logger
from arcor2.urdf import urdf_from_url
from arcor2_calibration.calibration import get_poses
from arcor2_calibration.robot import calibrate_robot

logger = get_logger(__name__)

MARKER_SIZE = float(os.getenv("ARCOR2_CALIBRATION_MARKER_SIZE", 0.091))
MARKER_ID = int(os.getenv("ARCOR2_CALIBRATION_MARKER_ID", 10))

_mock: bool = False

app = create_app(__name__)


@app.route("/calibrate/robot", methods=["PUT"])
def put_calibrate_robot() -> RespT:
    """Get calibration (camera pose wrt. marker)
    ---
    put:
        description: Get calibration
        tags:
           - Calibration
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

    """

    image = Image.open(request.files["image"].stream)
    args = CalibrateRobotArgs.from_json(request.files["args"].read())

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


@app.route("/calibrate/camera", methods=["PUT"])
def get_calibration() -> RespT:
    """Get calibration (camera pose wrt. marker)
    ---
    put:
        description: Get calibration
        tags:
           - Calibration
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
                    $ref: Pose

    """

    file = request.files["image"]

    camera_matrix = [
        [float(request.args["fx"]), 0.00000, float(request.args["cx"])],
        [0.00000, float(request.args["fy"]), float(request.args["cy"])],
        [0.00000, 0.00000, 1],
    ]

    image = Image.open(file.stream)

    dist_matrix = [float(val) for val in request.args.getlist("distCoefs")]

    if _mock:
        time.sleep(0.5)
        pose = Pose(Position(random.uniform(-0.5, 0.5), random.uniform(-0.5, 0.5), random.uniform(0.2, 1)))
    else:
        poses = get_poses(camera_matrix, dist_matrix, image, MARKER_SIZE)
        try:
            pose = poses[MARKER_ID]  # TODO this is just temporary (single-marker) solution
        except KeyError:
            return "Marker not found", 404

    return jsonify(pose.to_dict()), 200


def main() -> None:

    parser = argparse.ArgumentParser(description=SERVICE_NAME)
    parser.add_argument("-s", "--swagger", action="store_true", default=False)
    parser.add_argument("-m", "--mock", action="store_true", default=False)
    args = parser.parse_args()

    global _mock
    _mock = args.mock
    if _mock:
        logger.info("Starting as a mock!")

    run_app(
        app,
        SERVICE_NAME,
        arcor2_calibration.version(),
        arcor2_calibration.version(),
        port_from_url(CALIBRATION_URL),
        [Pose, CalibrateRobotArgs],
        args.swagger,
    )


if __name__ == "__main__":
    main()
