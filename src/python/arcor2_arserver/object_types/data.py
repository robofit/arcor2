from ast import AST
from dataclasses import dataclass, field
from typing import Dict, Optional, Type

from arcor2.exceptions import Arcor2Exception
from arcor2.object_types.abstract import Generic
from arcor2_arserver_data.objects import ObjectAction, ObjectTypeMeta
from arcor2_arserver_data.robot import RobotMeta


@dataclass
class ObjectTypeData:

    meta: ObjectTypeMeta
    type_def: Optional[Type[Generic]] = None
    actions: Dict[str, ObjectAction] = field(default_factory=dict)
    ast: Optional[AST] = None
    robot_meta: Optional[RobotMeta] = None

    def __post_init__(self) -> None:
        if not self.meta.disabled:
            assert self.type_def is not None
            assert self.ast is not None


class ObjTypeDict(dict):
    def __getitem__(self, object_type_id: str) -> ObjectTypeData:
        try:
            return super().__getitem__(object_type_id)
        except KeyError:
            raise Arcor2Exception(f"Unknown ObjectType: {object_type_id}.")


ObjectTypeDict = Dict[str, ObjectTypeData]
