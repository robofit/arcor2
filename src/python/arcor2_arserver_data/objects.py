from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from dataclasses_jsonschema import JsonSchemaMixin

from arcor2.data.common import ActionMetadata
from arcor2.data.object_type import ObjectModel, ObjectType, ParameterMeta
from arcor2.exceptions import Arcor2Exception


@dataclass
class ObjectTypeMeta(JsonSchemaMixin):
    """Metadata about object type, as it is used in server API."""

    type: str
    description: str = field(default_factory=str)
    built_in: bool = False
    base: str = field(default_factory=str)
    object_model: Optional[ObjectModel] = None  # can't use Models (Union) because of C# generator
    needs_parent_type: Optional[str] = None
    has_pose: bool = False
    abstract: bool = False
    disabled: bool = False
    problem: Optional[str] = None
    settings: list[ParameterMeta] = field(default_factory=list)
    modified: Optional[datetime] = None

    def to_object_type(self, source: str = "") -> ObjectType:

        ot = ObjectType(self.type, source, self.description)

        if self.object_model:
            ot.model = self.object_model.model().metamodel()

        return ot

    def parameters_dict(self) -> dict[str, ParameterMeta]:
        return {param.name: param for param in self.settings}

    def __post_init__(self) -> None:

        if self.object_model and (model := self.object_model.model()).id != self.type:
            raise Arcor2Exception(f"Object model id ({model.id}) must be equal to the ObjectType id ({self.type}).")


@dataclass
class ObjectAction(JsonSchemaMixin):

    name: str
    description: Optional[str] = None
    parameters: list[ParameterMeta] = field(default_factory=list)
    meta: ActionMetadata = field(default_factory=ActionMetadata)
    origins: Optional[str] = None
    returns: list[str] = field(default_factory=list)  # list of returned types
    disabled: bool = False
    problem: Optional[str] = None

    def parameter(self, param_name: str) -> ParameterMeta:

        for param in self.parameters:
            if param.name == param_name:
                return param
        raise Arcor2Exception("Parameter not found.")


ObjectActions = list[ObjectAction]
