from typing import Callable, List, Tuple, Any, Type

import horast
from typed_ast import ast3 as ast

from arcor2.data.common import Project, Scene
from arcor2.parameter_plugins.base import ParameterPlugin, ParameterPluginException, TypesDict
from arcor2.data.object_type import ActionParameterMeta
from arcor2.source.utils import find_function, find_asserts


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

    return None, None


def get_min_max(cls: Type[ParameterPlugin], param_meta: ActionParameterMeta, action_method: Callable, source: str) -> \
        None:

    tree = horast.parse(source)
    method_tree = find_function(action_method.__name__, tree)
    minimum, maximum = get_assert_minimum_maximum(find_asserts(method_tree), param_meta.name)

    for var in minimum, maximum:
        if var is not None and not isinstance(minimum, cls.type()):
            raise ParameterPluginException("Parameter bounds has incorrect type.")

    param_meta.minimum = minimum
    param_meta.maximum = maximum


class IntegerPlugin(ParameterPlugin):

    @classmethod
    def type(cls):
        return int

    @classmethod
    def type_name(cls) -> str:
        return "integer"

    @classmethod
    def meta(cls, param_meta: ActionParameterMeta, action_method: Callable, source: str) -> None:

        super(IntegerPlugin, cls).meta(param_meta, action_method, source)
        get_min_max(IntegerPlugin, param_meta, action_method, source)

    @classmethod
    def value(cls, type_defs: TypesDict, scene: Scene, project: Project, action_id: str, parameter_id: str) -> int:
        return super(IntegerPlugin, cls).value(type_defs, scene, project, action_id, parameter_id)
