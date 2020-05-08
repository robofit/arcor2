from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, List, Dict, Union, Set

from dataclasses_jsonschema import JsonSchemaMixin

from arcor2.data import DataException
from arcor2.data.common import ActionMetadata, Pose, Position


class Model3dType(Enum):

    NONE: str = "None"
    BOX: str = "Box"
    CYLINDER: str = "Cylinder"
    SPHERE: str = "Sphere"
    MESH: str = "Mesh"


@dataclass
class MetaModel3d(JsonSchemaMixin):

    id: str
    type: Model3dType

    def __post_init__(self) -> None:

        if isinstance(self.type, str):
            self.type = Model3dType[self.type.upper()]


@dataclass
class Model(JsonSchemaMixin):

    id: str

    @classmethod
    def type(cls) -> Model3dType:
        return Model3dType[cls.__name__.upper()]

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

        if self.model and self.model.type == Model3dType.NONE:
            self.model = None


@dataclass
class ObjectModel(JsonSchemaMixin):

    type: Model3dType
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
    disabled: bool = False
    problem: Optional[str] = None

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
class ActionParameterMeta(JsonSchemaMixin):

    name: str
    type: str
    dynamic_value: bool = False  # client should ask for allowed values using RPC
    dynamic_value_parents: Optional[Set[str]] = None
    description: Optional[str] = None
    default_value: Optional[str] = None
    extra: Optional[str] = None


@dataclass
class ObjectAction(JsonSchemaMixin):

    name: str
    description: Optional[str] = None
    parameters: List[ActionParameterMeta] = field(default_factory=list)
    meta: ActionMetadata = field(default_factory=ActionMetadata)
    origins: Optional[str] = None
    returns: Optional[str] = None
    disabled: bool = False
    problem: Optional[str] = None


ObjectTypeMetaDict = Dict[str, ObjectTypeMeta]
ObjectActions = List[ObjectAction]
ObjectActionsDict = Dict[str, ObjectActions]


@dataclass
class MeshFocusAction(JsonSchemaMixin):

    mesh_focus_points: List[Position]
    robot_space_points: List[Position]

    def __post_init__(self) -> None:

        assert len(self.mesh_focus_points) == len(self.robot_space_points)


@dataclass
class CollisionModels(JsonSchemaMixin):

    boxes: List[Box] = field(default_factory=list)
    spheres: List[Sphere] = field(default_factory=list)
    cylinders: List[Cylinder] = field(default_factory=list)
    meshes: List[Mesh] = field(default_factory=list)
