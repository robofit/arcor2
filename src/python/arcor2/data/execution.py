from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from dataclasses_jsonschema import JsonSchemaMixin


@dataclass
class PackageMeta(JsonSchemaMixin):

    name: str
    built: datetime
    executed: Optional[datetime] = None
