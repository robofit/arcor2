from dataclasses import dataclass

import numpy as np
from dataclasses_jsonschema import JsonSchemaMixin

from arcor2.exceptions import Arcor2Exception


@dataclass
class CameraParameters(JsonSchemaMixin):

    fx: float
    fy: float
    cx: float
    cy: float
    dist_coefs: list[float]  # (k1,k2,p1,p2[,k3[,k4,k5,k6],[s1,s2,s3,s4]])

    def __post_init__(self) -> None:

        if len(self.dist_coefs) not in (4, 5, 8, 12):
            raise Arcor2Exception("Unsupported number of distortion coefficients.")

    def as_camera_matrix(self) -> np.ndarray:

        return np.array(
            [
                [self.fx, 0.00000, self.cx],
                [0.00000, self.fy, self.cy],
                [0.00000, 0.00000, 1],
            ]
        )
