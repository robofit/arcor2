from typing import Optional, List, Dict, Union, Set
from enum import Enum

from arcor2.data import DataException
from arcor2.data.common import ActionMetadata, Pose, Position
from dataclasses import dataclass, field
from dataclasses_jsonschema import JsonSchemaMixin


class ModelTypeEnum(Enum):

    NONE: str = "None"
    BOX: str = "Box"
    CYLINDER: str = "Cylinder"
    SPHERE: str = "Sphere"
    MESH: str = "Mesh"


@dataclass
class MetaModel3d(JsonSchemaMixin):

    id: str
    type: ModelTypeEnum

    def __post_init__(self) -> None:

        if isinstance(self.type, str):
            self.type = ModelTypeEnum[self.type.upper()]


@dataclass
class Model(JsonSchemaMixin):

    id: str

    @classmethod
    def type(cls) -> ModelTypeEnum:
        return ModelTypeEnum[cls.__name__.upper()]

    def metamodel(self) -> MetaModel3d:
        return MetaModel3d(self.id, self.type())


@dataclass
class Box(Model):

    size_x: float
    size_y: float
    size_z: float


@dataclass
class Cylinder(Model):

    radius: float
    height: float


@dataclass
class Sphere(Model):
    radius: float


@dataclass
class Mesh(Model):

    uri: str
    focus_points: Optional[List[Pose]] = None


MeshList = List[Mesh]

Models = Union[Box, Sphere, Cylinder, Mesh]

MODEL_MAPPING = {Box.type(): Box,
                 Sphere.type(): Sphere,
                 Cylinder.type(): Cylinder,
                 Mesh.type(): Mesh}


@dataclass
class ObjectType(JsonSchemaMixin):
    """
    Object type, as it is stored in DB.
    """

    id: str
    source: str
    desc: Optional[str] = ""
    model: Optional[MetaModel3d] = None

    def __post_init__(self) -> None:  # TODO workaround for bug (?) in Storage

        if self.model and self.model.type == ModelTypeEnum.NONE:
            self.model = None


@dataclass
class ObjectModel(JsonSchemaMixin):

    type: ModelTypeEnum
    box: Optional[Box] = None
    cylinder: Optional[Cylinder] = None
    sphere: Optional[Sphere] = None
    mesh: Optional[Mesh] = None

    def model(self) -> Models:
        return getattr(self, str(self.type.value).lower())

    def __post_init__(self) -> None:

        models_list = [self.box, self.cylinder, self.sphere, self.mesh]

        if models_list.count(None) != len(models_list)-1:
            raise DataException("No model specified!")


@dataclass
class ObjectTypeMeta(JsonSchemaMixin):
    """
    Metadata about object type, as it is used in server API.
    """

    type: str
    description: str = field(default_factory=str)
    built_in: bool = False
    base: str = field(default_factory=str)
    object_model: Optional[ObjectModel] = None
    needs_services: Set[str] = field(default_factory=set)
    abstract: bool = False

    def to_object_type(self) -> ObjectType:

        ot = ObjectType(self.type, "", self.description)

        if self.object_model:

            if self.object_model.type == ModelTypeEnum.MESH:
                assert self.object_model.mesh
                m_id = self.object_model.mesh.id
            else:
                m_id = self.type

            ot.model = MetaModel3d(m_id, self.object_model.type)

        return ot


@dataclass
class ActionParameterMeta(JsonSchemaMixin):

    name: str
    type: str
    dynamic_value: bool = False  # client should ask for allowed values using RPC
    dynamic_value_parents: Optional[Set[str]] = None
    description: str = ""
    default_value: Optional[str] = None
    extra: Optional[str] = None


@dataclass
class ObjectAction(JsonSchemaMixin):  # TODO description (from docstring)

    name: str
    description: str = ""
    parameters: List[ActionParameterMeta] = field(default_factory=list)
    returns: str = "NoneType"
    origins: str = ""
    meta: ActionMetadata = field(default_factory=ActionMetadata)


ObjectTypeMetaDict = Dict[str, ObjectTypeMeta]
ObjectActions = List[ObjectAction]
ObjectActionsDict = Dict[str, ObjectActions]


@dataclass
class MeshFocusAction(JsonSchemaMixin):

    mesh_focus_points: List[Position]
    robot_space_points: List[Position]

    def __post_init__(self) -> None:

        assert len(self.mesh_focus_points) == len(self.robot_space_points)
