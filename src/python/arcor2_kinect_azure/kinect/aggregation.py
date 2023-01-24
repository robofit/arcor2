import math
from math import radians, tan
from typing import Tuple

import pyk4a
from flask import Request
from pyk4a import ColorResolution, PyK4ACapture

from arcor2.data.common import BodyJointId, Direction, Position
from arcor2.exceptions import Arcor2Exception
from arcor2.logging import get_logger
from arcor2_kinect_azure import ARCOR2_KINECT_AZURE_LOG_LEVEL
from arcor2_kinect_azure.exceptions import InvalidDirection
from arcor2_kinect_azure.kinect.common import parse_skeleton
from arcor2_kinect_azure_data.aggregation import MovingDirection
from arcor2_kinect_azure_data.joint import BodyJoint, JointValid

log = get_logger(__name__, ARCOR2_KINECT_AZURE_LOG_LEVEL)


def get_distance_coeffs(distance: float) -> Tuple[float, float]:
    """We need to account for the camera curvature.

    :return: Horizontal coefficient, vertical coefficient
    """

    def map_resolution_to_radians(resolution: ColorResolution) -> Tuple[float, float]:
        assert resolution in (r.value for r in ColorResolution)
        assert resolution != 0
        return {
            ColorResolution.RES_2160P: (radians(90), radians(59)),
            ColorResolution.RES_1440P: (radians(90), radians(59)),
            ColorResolution.RES_1080P: (radians(90), radians(59)),
            ColorResolution.RES_720P: (radians(90), radians(59)),
            ColorResolution.RES_3072P: (radians(90), radians(74.3)),
            ColorResolution.RES_1536P: (radians(90), radians(74.3)),
        }[resolution]

    from arcor2_kinect_azure import app

    kinect = app.KINECT
    assert kinect is not None
    config = kinect.config()
    horizontal_radians, vertical_radians = map_resolution_to_radians(config.color_resolution)

    def compute_coef(rads: float) -> float:
        return tan(rads / 2) * 2 * (distance / 1000 + 1)

    return compute_coef(horizontal_radians), compute_coef(vertical_radians)


class FailedToComputeError(Arcor2Exception):
    pass


class Moving(MovingDirection):
    """Class for computing moving direction from captures."""

    def __init__(
        self,
        compute_buffer: list[PyK4ACapture],
        body_index: int = 0,
        joint_index: int = BodyJointId.SPINE_CHEST,
        num_samples: int | None = None,
        best_effort: bool = False,
        camera_fps: pyk4a.FPS = pyk4a.FPS.FPS_30,
    ) -> None:
        fps = 30 if camera_fps is pyk4a.FPS.FPS_30 else 15 if camera_fps is pyk4a.FPS.FPS_15 else 5

        self._compute_buffer = compute_buffer

        self.body_index: int = body_index
        self.joint_index: int = joint_index
        self.num_samples: int = num_samples or 5

        self._best_effort: bool = best_effort

        self._camera_fps = fps

    def compute(self) -> None:
        log.debug(f"Computing for {self.body_index=}, {self.joint_index=}")
        if self.num_samples < 2:
            raise FailedToComputeError("Not enough data")

        relevant_buffer: list[BodyJoint] = []
        skip_counter: int = 0

        for capture in self._compute_buffer[::-1]:
            skeleton = parse_skeleton(capture, self.body_index)
            if skeleton is None:
                if self._best_effort is False and skip_counter > 4:
                    log.error("Multiple captures in sequence are missing bodies")
                    raise FailedToComputeError("No body in frame")
                skip_counter += 1
                continue
            skip_counter = 0

            joint: BodyJoint = BodyJoint.from_joint(skeleton[self.joint_index])
            if joint.valid != JointValid.VALID:
                log.error(f"{joint} is invalid")
                continue

            relevant_buffer.append(joint)

            if len(relevant_buffer) == self.num_samples:
                break

        if len(relevant_buffer) != self.num_samples and self._best_effort is False:
            return

        if len(relevant_buffer) < 2:
            log.error(f"{len(relevant_buffer)=}, unable to compute direction")
            return

        pos = relevant_buffer[0].position
        self.position = pos

        def get_speed(buffer: list[float], coef: float = 1) -> float:
            _sum: float = 0
            for i in range(len(buffer) - 1):
                _sum += buffer[i] - buffer[i + 1]
            return _sum / len(buffer) * coef

        _horizontal_coef, _vertical_coef = get_distance_coeffs(pos.z)

        x_speed = get_speed([b.position.x for b in relevant_buffer], _horizontal_coef)
        y_speed = get_speed([b.position.y for b in relevant_buffer], _vertical_coef)
        z_speed = get_speed([b.position.z for b in relevant_buffer])

        speed_coef = self._camera_fps / self.num_samples

        self.speed = Position(x=x_speed * speed_coef, y=y_speed * speed_coef, z=z_speed * speed_coef)


class DirectionWithSpeed:
    def __init__(self, direction: Direction, speed: float) -> None:
        self.direction = direction
        # Speed in m/s
        self.speed = speed

    @classmethod
    def from_moving(cls, moving: Moving) -> "DirectionWithSpeed":
        speed = math.sqrt(moving.speed.x**2 + moving.speed.y**2 + moving.speed.z**2)
        return cls(Direction(moving.speed.x, moving.speed.y, moving.speed.z), speed)

    @classmethod
    def from_request(cls, request: Request) -> "DirectionWithSpeed":
        speed = float(request.args.get("speed") or 0.1)
        direction = Direction.from_json(request.data)

        return cls(direction, speed)

    def is_zero(self) -> bool:
        if self.direction.x == 0.0 and self.direction.y == 0.0 and self.direction.z == 0.0:
            return True
        else:
            return False

    def is_faster_than(self, other: "DirectionWithSpeed", deviation: float = 0.1) -> bool:
        if not 0.0 <= deviation <= 1.0:
            raise ValueError("Invalid deviation passed")

        def check_matching_directions() -> bool:
            for s, o in [
                (self.direction.x, other.direction.x),
                (self.direction.y, other.direction.y),
                (self.direction.z, other.direction.z),
            ]:
                if s < 0 < o:
                    return False
                elif o < 0 < s:
                    return False
            return True

        if not check_matching_directions():
            return False

        def get_hypotenuse(d: Direction) -> float:
            # c side of right triangle
            return math.sqrt(d.x**2 + d.y**2 + d.z**2)

        # Scale direction based on x
        self_scale = 1.0
        if self.direction.x != 0.0:
            other_scale = other.direction.x / self.direction.x
        elif self.direction.y != 0.0:
            other_scale = other.direction.y / self.direction.y
        elif self.direction.z != 0.0:
            other_scale = other.direction.z / self.direction.z
        else:
            raise InvalidDirection(f"{self.direction}")

        def get_normalized_direction_by_scale(d: Direction, scale: float) -> Direction:
            return Direction(d.x / scale, d.y / scale, d.z / scale)

        self_n_d = get_normalized_direction_by_scale(self.direction, self_scale)
        other_n_d = get_normalized_direction_by_scale(other.direction, other_scale)

        self_c = get_hypotenuse(self_n_d)
        other_c = get_hypotenuse(other_n_d)

        # check if same direction
        if other_c * (1.0 - deviation) < self_c < other_c / (1.0 - deviation):
            if self.speed > other.speed:
                return True
        return False
