from typing import Any, Callable, List

from typed_ast import ast3 as ast

from arcor2.cached import CachedProject as CProject, CachedScene as CScene
from arcor2.data.object_type import ActionParameterMeta
from arcor2.parameter_plugins.base import ParameterPlugin, TypesDict
from arcor2.parameter_plugins.integer import get_min_max
from arcor2.parameter_plugins.list import ListParameterPlugin, get_type_name


class DoublePlugin(ParameterPlugin):

    @classmethod
    def type(cls) -> Any:
        return float

    @classmethod
    def type_name(cls) -> str:
        return "double"

    @classmethod
    def meta(cls, param_meta: ActionParameterMeta, action_method: Callable, action_node: ast.FunctionDef) -> None:
        super(DoublePlugin, cls).meta(param_meta, action_method, action_node)
        get_min_max(DoublePlugin, param_meta, action_method, action_node)

    @classmethod
    def value(cls, type_defs: TypesDict, scene: CScene, project: CProject, action_id: str, parameter_id: str) \
            -> float:
        return cls.type()(super(DoublePlugin, cls).value(type_defs, scene, project, action_id, parameter_id))


class DoubleListPlugin(ListParameterPlugin):

    @classmethod
    def type(cls):
        return List[float]

    @classmethod
    def type_name(cls) -> str:
        return get_type_name(DoublePlugin)

    @classmethod
    def meta(cls, param_meta: ActionParameterMeta, action_method: Callable, action_node: ast.FunctionDef) -> None:
        super(DoubleListPlugin, cls).meta(param_meta, action_method, action_node)

    @classmethod
    def value(cls, type_defs: TypesDict, scene: CScene, project: CProject, action_id: str, parameter_id: str) \
            -> List[float]:
        return super(DoubleListPlugin, cls).value(type_defs, scene, project, action_id, parameter_id)
