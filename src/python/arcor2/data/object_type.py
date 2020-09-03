from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, Set, Union

from dataclasses_jsonschema import JsonSchemaMixin

from arcor2.data import DataException
from arcor2.data.common import Pose


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

MODEL_MAPPING = {Box.type(): Box, Sphere.type(): Sphere, Cylinder.type(): Cylinder, Mesh.type(): Mesh}


@dataclass
class ObjectType(JsonSchemaMixin):
    """Object type, as it is stored in DB."""

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

        if models_list.count(None) != len(models_list) - 1:
            raise DataException("No model specified!")


@dataclass
class CollisionModels(JsonSchemaMixin):

    boxes: List[Box] = field(default_factory=list)
    spheres: List[Sphere] = field(default_factory=list)
    cylinders: List[Cylinder] = field(default_factory=list)
    meshes: List[Mesh] = field(default_factory=list)


@dataclass
class ParameterMeta(JsonSchemaMixin):

    name: str
    type: str
    dynamic_value: bool = False  # client should ask for allowed values using RPC
    dynamic_value_parents: Optional[Set[str]] = None
    description: Optional[str] = None
    default_value: Optional[str] = None
    extra: Optional[str] = None
    children: List["ParameterMeta"] = field(default_factory=list)
