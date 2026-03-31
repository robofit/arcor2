from dataclasses import dataclass, field
from typing import Any

import humps
from flask import request

from arcor2.data import common, object_type


@dataclass
class CollisionSceneObject:
    model: object_type.Models
    pose: common.Pose
    metadata: dict[str, Any] = field(default_factory=dict)


def parse_collision_body() -> tuple[common.Pose, dict[str, Any]]:
    body = humps.decamelize(request.json)

    if "pose" in body:
        pose = common.Pose.from_dict(body["pose"])
        metadata = body.get("metadata", {}) or {}
        return pose, metadata

    return common.Pose.from_dict(body), {}
