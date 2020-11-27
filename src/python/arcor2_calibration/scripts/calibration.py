#!/usr/bin/env python3

import argparse
import json
import os
from typing import Tuple, Union

from apispec import APISpec
from apispec_webframeworks.flask import FlaskPlugin
from arcor2_calibration_data import CALIBRATION_URL, SERVICE_NAME
from dataclasses_jsonschema.apispec import DataclassesPlugin
from flask import Flask, Response, jsonify, request
from flask_cors import CORS
from flask_swagger_ui import get_swaggerui_blueprint
from PIL import Image

import arcor2_calibration
from arcor2.data.common import Pose
from arcor2.helpers import port_from_url
from arcor2.logging import get_logger
from arcor2_calibration.calibration import get_poses

logger = get_logger(__name__)

# Create an APISpec
spec = APISpec(
    title=SERVICE_NAME,
    version=arcor2_calibration.version(),
    openapi_version="3.0.2",
    plugins=[FlaskPlugin(), DataclassesPlugin()],
)

RETURN_TYPE = Union[Tuple[str, int], Response, Tuple[Response, int]]

MARKER_SIZE = float(os.getenv("ARCOR2_CALIBRATION_MARKER_SIZE", 0.09))
MARKER_ID = int(os.getenv("ARCOR2_CALIBRATION_MARKER_ID", 10))

app = Flask(__name__)
CORS(app)


@app.route("/swagger/api/swagger.json", methods=["GET"])
def get_swagger() -> str:
    return json.dumps(spec.to_dict())


@app.route("/calibration", methods=["PUT"])
def get_calibration() -> RETURN_TYPE:
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
                collectionFormat: multi
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
    poses = get_poses(camera_matrix, dist_matrix, image, MARKER_SIZE)
    try:
        pose = poses[MARKER_ID]  # TODO this is just temporary (single-marker) solution
    except KeyError:
        return "Marker not found", 404

    return jsonify(pose.to_dict()), 200


with app.test_request_context():
    spec.path(view=get_calibration)

spec.components.schema(Pose.__name__, schema=Pose)


def main() -> None:

    parser = argparse.ArgumentParser(description=SERVICE_NAME)
    parser.add_argument("-s", "--swagger", action="store_true", default=False)
    args = parser.parse_args()

    if args.swagger:
        print(spec.to_yaml())
        return

    SWAGGER_URL = "/swagger"

    swaggerui_blueprint = get_swaggerui_blueprint(
        SWAGGER_URL, "./api/swagger.json"  # Swagger UI static files will be mapped to '{SWAGGER_URL}/dist/'
    )

    # Register blueprint at URL
    app.register_blueprint(swaggerui_blueprint, url_prefix=SWAGGER_URL)

    app.run(host="0.0.0.0", port=port_from_url(CALIBRATION_URL))


if __name__ == "__main__":
    main()
