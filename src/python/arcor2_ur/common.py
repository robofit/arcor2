from dataclasses import dataclass, field
from typing import Any

import humps
from flask import request

from arcor2.data import common, object_type
from arcor2.data.common import StrEnum
from arcor2_ur.exceptions import UrGeneral


class GraspPosition(StrEnum):
    TOP = "TOP"
    RIGHT = "RIGHT"
    LEFT = "LEFT"
    FRONT = "FRONT"
    BACK = "BACK"
    BOTTOM = "BOTTOM"
    ALL = "ALL"


class EffectorType(StrEnum):
    SUCK = "SUCK"


class GraspableState(StrEnum):
    """Logical state of a graspable object in the scene.

    WORLD
        Free object in the environment. Acts as a collision obstacle.

    RESERVED
        Reserved by the robot. Waiting for pickup.

    HIDDEN
        Object is hidden so the robot can attach it.
        This state is used only in ros_worker file.

    ATTACHED
        Attached to the robot end-effector.
    """

    WORLD = "WORLD"
    RESERVED = "RESERVED"
    HIDDEN = "HIDDEN"
    ATTACHED = "ATTACHED"


class GraspableSource(StrEnum):
    """Source of the object pose information.

    CAMERA
        Detected by a vision system.

    FIXED
        Predefined static object.

    OTHER
        Arbitrary or unspecified source (e.g., tests, debugging, simulations, or other scenarios).
    """

    CAMERA = "CAMERA"
    FIXED = "FIXED"
    OTHER = "OTHER"


@dataclass
class CollisionSceneObject:
    model: object_type.Models
    pose: common.Pose
    metadata: dict[str, Any] = field(default_factory=dict)


def parse_collision_body() -> tuple[common.Pose, dict[str, Any]]:
    if not isinstance(request.json, dict):
        raise UrGeneral("Body should be a JSON dict containing Pose or pose and metadata.")

    body = humps.decamelize(request.json)

    if "pose" in body:
        pose = common.Pose.from_dict(body["pose"])
        metadata = body.get("metadata", {}) or {}
        return pose, metadata

    return common.Pose.from_dict(body), {}
