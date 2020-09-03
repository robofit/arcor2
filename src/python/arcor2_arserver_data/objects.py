from dataclasses import dataclass, field
from typing import List, Optional

from dataclasses_jsonschema import JsonSchemaMixin

from arcor2.data.common import ActionMetadata
from arcor2.data.object_type import MetaModel3d, Model3dType, ObjectModel, ObjectType, ParameterMeta
from arcor2.exceptions import Arcor2Exception


@dataclass
class ObjectTypeMeta(JsonSchemaMixin):
    """Metadata about object type, as it is used in server API."""

    type: str
    description: str = field(default_factory=str)
    built_in: bool = False
    base: str = field(default_factory=str)
    object_model: Optional[ObjectModel] = None
    needs_parent_type: Optional[str] = None
    has_pose: bool = False
    abstract: bool = False
    disabled: bool = False
    problem: Optional[str] = None
    settings: List[ParameterMeta] = field(default_factory=list)

    def to_object_type(self) -> ObjectType:

        ot = ObjectType(self.type, "", self.description)

        if self.object_model:

            if self.object_model.type == Model3dType.MESH:
                assert self.object_model.mesh
                m_id = self.object_model.mesh.id
            else:
                m_id = self.type

            ot.model = MetaModel3d(m_id, self.object_model.type)

        return ot


@dataclass
class ObjectAction(JsonSchemaMixin):

    name: str
    description: Optional[str] = None
    parameters: List[ParameterMeta] = field(default_factory=list)
    meta: ActionMetadata = field(default_factory=ActionMetadata)
    origins: Optional[str] = None
    returns: List[str] = field(default_factory=list)  # list of returned types
    disabled: bool = False
    problem: Optional[str] = None

    def parameter(self, param_name: str) -> ParameterMeta:

        for param in self.parameters:
            if param.name == param_name:
                return param
        raise Arcor2Exception("Parameter not found.")


ObjectActions = List[ObjectAction]
