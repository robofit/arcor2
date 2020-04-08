from typing import Set, Optional, Dict
from dataclasses import dataclass, field

from dataclasses_jsonschema import JsonSchemaMixin


@dataclass
class ServiceType(JsonSchemaMixin):
    """
    Service type, as it is stored in DB.
    """

    id: str
    source: str
    desc: Optional[str] = ""


@dataclass
class ServiceTypeMeta(JsonSchemaMixin):
    """
    Metadata about object type, as it is used in server API.
    """

    type: str
    description: str = field(default_factory=str)
    configuration_ids: Set[str] = field(default_factory=set)
    built_in: bool = False
    disabled: bool = False
    problem: Optional[str] = None


ServiceTypeMetaDict = Dict[str, ServiceTypeMeta]
