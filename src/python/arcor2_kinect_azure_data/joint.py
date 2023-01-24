from dataclasses import dataclass
from enum import IntEnum

import numpy as np
from dataclasses_jsonschema import JsonSchemaMixin

from arcor2.data.common import Orientation, Position
from arcor2.exceptions import Arcor2Exception


class InvalidConfidence(Arcor2Exception):
    pass


class InvalidMeasurement(Arcor2Exception):
    pass


class JointConfidence(IntEnum):
    NONE = 0
    LOW = 1
    MEDIUM = 2
    HIGH = 3

    @classmethod
    def from_joint(cls, ndarray: np.ndarray) -> int:
        value = int(ndarray[7])
        if value not in (v.value for v in cls):
            raise InvalidConfidence(f"Confidence joint value {value} is invalid")
        return value


class JointValid(IntEnum):
    INVALID = 0
    VALID = 1

    @classmethod
    def from_joint(cls, ndarray: np.ndarray) -> int:
        value = int(ndarray[10])
        if value not in (v.value for v in cls):
            raise InvalidMeasurement(f"Got invalid joint value for field 'valid': {value}")
        return value


@dataclass
class BodyJoint(JsonSchemaMixin):
    position: Position
    orientation: Orientation
    confidence_level: int
    position_image_0: float
    position_image_1: float
    valid: int

    @classmethod
    def from_joint(cls, ndarray: np.ndarray) -> "BodyJoint":
        return cls(
            position=Position(x=float(ndarray[0]) / 1000.0, y=float(ndarray[1]) / 1000.0, z=float(ndarray[2]) / 1000.0),
            orientation=Orientation(w=float(ndarray[3]), x=float(ndarray[4]), y=float(ndarray[5]), z=float(ndarray[6])),
            confidence_level=JointConfidence.from_joint(ndarray),
            position_image_0=float(ndarray[8]),
            position_image_1=float(ndarray[9]),
            valid=JointValid.from_joint(ndarray),
        )


__all__ = [
    "InvalidConfidence",
    "InvalidMeasurement",
    "JointConfidence",
    "JointValid",
    "BodyJoint",
]
