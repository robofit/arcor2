from typing import Optional, List, Dict, Union
from enum import Enum

from arcor2.data import DataException
from arcor2.data.common import ActionMetadata, Pose, Position, ActionParameterTypeEnum
from dataclasses import dataclass, field
from dataclasses_jsonschema import JsonSchemaMixin


@dataclass
class ServiceMeta(JsonSchemaMixin):  # TODO ObjecTypeMeta could be probably derived from this
    """
    Metadata about object type, as it is used in server API.
    """

    type: str
    description: str = field(default_factory=str)
