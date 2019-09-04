from typing import Optional, List, Dict, Union
from enum import Enum

from arcor2.data.common import ActionMetadata, Pose, Position, Orientation
from dataclasses import dataclass, field
from dataclasses_jsonschema import JsonSchemaMixin


class ModelTypeEnum(Enum):

    BOX: str = "box"
    CYLINDER: str = "cylinder"
    SPHERE: str = "sphere"


@dataclass
class MetaModel3d(JsonSchemaMixin):

    id: str
    type: ModelTypeEnum

    def __post_init__(self):

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
    pose: Pose = Pose(Position(0, 0, 0), Orientation(0, 0, 0, 1))  # TODO remove!!!


@dataclass
class Cylinder(Model):

    radius: float
    height: float
    pose: Pose = Pose(Position(0, 0, 0), Orientation(0, 0, 0, 1))  # TODO remove!!!


@dataclass
class Sphere(Model):
    radius: float
    pose: Pose = Pose(Position(0, 0, 0), Orientation(0, 0, 0, 1))  # TODO remove!!!


Models = Union[Box, Sphere, Cylinder]

MODEL_MAPPING = {Box.type(): Box,
                 Sphere.type(): Sphere,
                 Cylinder.type(): Cylinder}


@dataclass
class ObjectType(JsonSchemaMixin):
    """
    Object type, as it is stored in DB.
    """

    id: str
    source: str
    desc: Optional[str] = ""
    model: Optional[MetaModel3d] = None


@dataclass
class ObjectModel(JsonSchemaMixin):

    type: ModelTypeEnum
    box: Optional[Box] = None
    cylinder: Optional[Cylinder] = None
    sphere: Optional[Sphere] = None

    def model(self) -> Models:
        return getattr(self, str(self.type.value))


@dataclass
class ObjectTypeMeta(JsonSchemaMixin):
    """
    Metadata about object type, as it is used in server API.
    """

    type: str
    description: str = field(default_factory=str)
    built_in: bool = False
    base: str = field(default_factory=str)
    model: Optional[ObjectModel] = None

    def to_object_type(self) -> ObjectType:

        ot = ObjectType(self.type, "", self.description)

        if self.model:
            ot.model = MetaModel3d(self.type, self.model.type)

        return ot


@dataclass
class ObjectActionArgs(JsonSchemaMixin):

    name: str
    type: str


@dataclass
class ObjectAction(JsonSchemaMixin):

    name: str
    action_args: List[ObjectActionArgs] = field(default_factory=list)
    returns: str = "NoneType"
    origins: str = ""
    meta: ActionMetadata = field(default_factory=ActionMetadata)


ObjectTypeMetaDict = Dict[str, ObjectTypeMeta]
ObjectActions = List[ObjectAction]
ObjectActionsDict = Dict[str, ObjectActions]
