from dataclasses import dataclass, field
from datetime import datetime

from dataclasses_jsonschema import JsonSchemaMixin

from arcor2.data.execution import PackageMeta


@dataclass
class PackageSummary(JsonSchemaMixin):

    id: str
    project_id: str
    modified: datetime = field(
        metadata=dict(description="Last modification of the project embedded in the execution package.")
    )
    package_meta: PackageMeta = field(metadata=dict(description="Content of 'package.json'."))
