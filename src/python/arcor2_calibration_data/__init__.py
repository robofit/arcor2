import os
from dataclasses import dataclass
from typing import List

from dataclasses_jsonschema import JsonSchemaMixin

from arcor2 import package_version

PORT = int(os.getenv("ARCOR2_CALIBRATION_PORT", 5014))
SERVICE_NAME = "ARCOR2 Calibration Service"


@dataclass
class CameraParameters(JsonSchemaMixin):

    fx: float
    fy: float
    cx: float
    cy: float
    dist_coefs: List[float]


def version() -> str:
    return package_version(__name__)
