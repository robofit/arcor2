from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from dataclasses_jsonschema import JsonSchemaMixin

from arcor2.data.execution import PackageMeta


@dataclass
class ProjectMeta(JsonSchemaMixin):
    """Provides data about the project embedded in the execution package."""

    id: str
    name: str
    modified: datetime = field(metadata=dict(description="Last modification."))


@dataclass
class PackageSummary(JsonSchemaMixin):

    id: str
    package_meta: PackageMeta = field(metadata=dict(description="Content of 'package.json'."))
    project_meta: Optional[ProjectMeta] = None
