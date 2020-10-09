from dataclasses import dataclass, field
from typing import Dict, Optional, Type

from typed_ast.ast3 import AST

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


ObjectTypeDict = Dict[str, ObjectTypeData]
