from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from dataclasses_jsonschema import JsonSchemaMixin

from arcor2.data import common, object_type


@dataclass
class PackageInfo(JsonSchemaMixin):

    package_id: str
    package_name: str
    scene: common.Scene
    project: common.Project
    collision_models: object_type.CollisionModels = field(default_factory=object_type.CollisionModels)


@dataclass
class PackageMeta(JsonSchemaMixin):

    name: str
    built: datetime
    executed: Optional[datetime] = None
