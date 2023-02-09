from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional

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

    def __post_init__(self) -> None:

        dims = [self.size_x, self.size_y, self.size_z]

        if [val for val in dims if val < 0]:
            raise DataException("Dimensions has to be positive.")

        if len([val for val in dims if val > 0]) < 2:
            raise DataException("Only one dimension of a box can be zero.")


@dataclass
class Cylinder(Model):

    radius: float
    height: float

    def __post_init__(self) -> None:

        if [val for val in [self.radius, self.height] if val <= 0]:
            raise DataException("Dimensions has to be positive.")


@dataclass
class Sphere(Model):
    radius: float

    def __post_init__(self) -> None:

        if self.radius <= 0:
            raise DataException("Radius has to be positive.")


@dataclass
class Mesh(Model):

    asset_id: str
    focus_points: Optional[list[Pose]] = None


MeshList = list[Mesh]

PrimitiveModels = Box | Sphere | Cylinder
Models = Box | Sphere | Cylinder | Mesh

MODEL_MAPPING: dict[Model3dType, type[Box] | type[Sphere] | type[Cylinder] | type[Mesh]] = {
    Box.type(): Box,
    Sphere.type(): Sphere,
    Cylinder.type(): Cylinder,
    Mesh.type(): Mesh,
}


@dataclass
class ObjectType(JsonSchemaMixin):
    """Object type, as it is stored in DB."""

    id: str
    source: str
    name: str = field(init=False)

    description: Optional[str] = None
    model: Optional[MetaModel3d] = None

    created: Optional[datetime] = None
    modified: Optional[datetime] = None

    def __post_init__(self) -> None:

        self.name = self.id  # name makes no sense for ObjectType but is required by the Project service

        # TODO workaround for bug (?) in Project service
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

        assert self.type != Model3dType.NONE
        return getattr(self, str(self.type.value).lower())

    def __post_init__(self) -> None:

        models_list = [self.box, self.cylinder, self.sphere, self.mesh]

        if models_list.count(None) != len(models_list) - 1:
            raise DataException("No model specified!")


@dataclass
class CollisionModels(JsonSchemaMixin):

    boxes: list[Box] = field(default_factory=list)
    spheres: list[Sphere] = field(default_factory=list)
    cylinders: list[Cylinder] = field(default_factory=list)
    meshes: list[Mesh] = field(default_factory=list)


@dataclass
class ParameterMeta(JsonSchemaMixin):

    name: str
    type: str
    dynamic_value: bool = False  # client should ask for allowed values using RPC
    dynamic_value_parents: Optional[set[str]] = None
    description: Optional[str] = None
    default_value: Optional[str] = None
    extra: Optional[str] = None
    # TODO not supported by AREditor, leads to Unable to create schema for 'ParameterMeta'
    # children: list[ParameterMeta] = field(default_factory=list)
