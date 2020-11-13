from typing import Any, Callable, List

from typed_ast import ast3 as ast

from arcor2.cached import CachedProject as CProject
from arcor2.cached import CachedScene as CScene
from arcor2.data.object_type import ParameterMeta
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
    def meta(cls, param_meta: ParameterMeta, action_method: Callable, action_node: ast.FunctionDef) -> None:
        super(DoublePlugin, cls).meta(param_meta, action_method, action_node)
        get_min_max(cls, param_meta, action_method, action_node)

    @classmethod
    def parameter_value(
        cls, type_defs: TypesDict, scene: CScene, project: CProject, action_id: str, parameter_id: str
    ) -> float:
        return super(DoublePlugin, cls).parameter_value(type_defs, scene, project, action_id, parameter_id)

    @classmethod
    def _value_from_json(cls, value: str) -> float:
        return super(DoublePlugin, cls)._value_from_json(value)


class DoubleListPlugin(ListParameterPlugin):
    @classmethod
    def type(cls):
        return List[float]

    @classmethod
    def type_name(cls) -> str:
        return get_type_name(DoublePlugin)  # type: ignore

    @classmethod
    def meta(cls, param_meta: ParameterMeta, action_method: Callable, action_node: ast.FunctionDef) -> None:
        super(DoubleListPlugin, cls).meta(param_meta, action_method, action_node)

    @classmethod
    def parameter_value(
        cls, type_defs: TypesDict, scene: CScene, project: CProject, action_id: str, parameter_id: str
    ) -> List[float]:
        return super(DoubleListPlugin, cls).parameter_value(type_defs, scene, project, action_id, parameter_id)
