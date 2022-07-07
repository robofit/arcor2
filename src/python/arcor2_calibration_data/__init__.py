import os
from dataclasses import dataclass

from dataclasses_jsonschema import JsonSchemaMixin

from arcor2 import package_version
from arcor2.data.common import Pose

CALIBRATION_URL = os.getenv("ARCOR2_CALIBRATION_URL", "http://localhost:5014")
SERVICE_NAME = "ARCOR2 Calibration Web API"


def version() -> str:
    return package_version(__name__)


@dataclass
class Corner(JsonSchemaMixin):

    x: float
    y: float


@dataclass
class MarkerCorners(JsonSchemaMixin):

    marker_id: int
    corners: list[Corner]


@dataclass
class EstimatedPose(JsonSchemaMixin):

    pose: Pose
    quality: float
