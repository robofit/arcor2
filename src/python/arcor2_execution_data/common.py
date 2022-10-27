from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

from dataclasses_jsonschema import JsonSchemaMixin

from arcor2.data.common import Project
from arcor2.data.execution import PackageMeta


@dataclass
class ProjectMeta(JsonSchemaMixin):
    """Provides data about the project embedded in the execution package."""

    id: str
    name: str
    description: str
    modified: datetime = field(metadata=dict(description="Last modification."))

    @classmethod
    def from_project(cls, project: Project) -> ProjectMeta:
        return ProjectMeta(
            project.id,
            project.name,
            project.description,
            project.modified if project.modified is not None else datetime.fromtimestamp(0, tz=timezone.utc),
        )


@dataclass
class PackageSummary(JsonSchemaMixin):

    id: str
    package_meta: PackageMeta = field(metadata=dict(description="Content of 'package.json'."))
    project_meta: None | ProjectMeta = None
