from dataclasses import dataclass
from typing import Any, Callable, List, Tuple, Type

from dataclasses_jsonschema import JsonSchemaMixin
from typed_ast import ast3 as ast

from arcor2.cached import CachedProject as CProject
from arcor2.cached import CachedScene as CScene
from arcor2.data.object_type import ParameterMeta
from arcor2.parameter_plugins.base import ParameterPlugin, ParameterPluginException, TypesDict
from arcor2.parameter_plugins.list import ListParameterPlugin, get_type_name
from arcor2.source.utils import find_asserts


@dataclass
class IntegerParameterExtra(JsonSchemaMixin):

    minimum: Any
    maximum: Any


class AssertNotFound(ParameterPluginException):
    pass


def get_assert_minimum_maximum(asserts: List[ast.Assert], param_name: str) -> Tuple[Any, Any]:

    # Assert(test=Compare(left=Num(n=0), ops=[LtE(), LtE()], comparators=[Name(id='speed', ctx=Load()), Num(n=100)]))

    for ass in asserts:

        if not isinstance(ass.test, ast.Compare):
            continue

        if len(ass.test.comparators) != 2:
            continue

        if len(ass.test.ops) != 2:
            continue

        err = False
        for op in ass.test.ops:
            if not isinstance(op, ast.LtE):
                err = True
                break
        if err:
            continue

        try:
            if ass.test.comparators[0].id == param_name:  # type: ignore
                return ass.test.left.n, ass.test.comparators[1].n  # type: ignore
        except AttributeError:
            continue

    raise AssertNotFound()


def get_min_max(
    cls: Type[ParameterPlugin], param_meta: ParameterMeta, action_method: Callable, action_node: ast.FunctionDef
) -> None:

    try:
        minimum, maximum = get_assert_minimum_maximum(find_asserts(action_node), param_meta.name)
    except AssertNotFound:
        return

    for var in minimum, maximum:
        if not isinstance(var, cls.type()):
            raise ParameterPluginException("Parameter bounds has incorrect type.")

    param_meta.extra = IntegerParameterExtra(minimum, maximum).to_json()


class IntegerPlugin(ParameterPlugin):
    @classmethod
    def type(cls) -> Any:
        return int

    @classmethod
    def type_name(cls) -> str:
        return "integer"

    @classmethod
    def meta(cls, param_meta: ParameterMeta, action_method: Callable, action_node: ast.FunctionDef) -> None:

        super(IntegerPlugin, cls).meta(param_meta, action_method, action_node)
        get_min_max(cls, param_meta, action_method, action_node)

    @classmethod
    def parameter_value(
        cls, type_defs: TypesDict, scene: CScene, project: CProject, action_id: str, parameter_id: str
    ) -> int:
        return super(IntegerPlugin, cls).parameter_value(type_defs, scene, project, action_id, parameter_id)

    @classmethod
    def _value_from_json(cls, value: str) -> int:
        return super(IntegerPlugin, cls)._value_from_json(value)


class IntegerListPlugin(ListParameterPlugin):
    @classmethod
    def type(cls):
        return List[int]

    @classmethod
    def type_name(cls) -> str:
        return get_type_name(IntegerPlugin)  # type: ignore

    @classmethod
    def meta(cls, param_meta: ParameterMeta, action_method: Callable, action_node: ast.FunctionDef) -> None:
        super(IntegerListPlugin, cls).meta(param_meta, action_method, action_node)

    @classmethod
    def parameter_value(
        cls, type_defs: TypesDict, scene: CScene, project: CProject, action_id: str, parameter_id: str
    ) -> List[int]:
        return super(IntegerListPlugin, cls).parameter_value(type_defs, scene, project, action_id, parameter_id)
