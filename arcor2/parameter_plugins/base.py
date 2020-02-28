import abc
from typing import Callable, Tuple, Any, Dict, Union, Type
import json

from typed_ast import ast3 as ast

from arcor2.exceptions import Arcor2Exception
from arcor2.data.common import ActionParameter, Project, Scene
from arcor2.data.object_type import ActionParameterMeta
from arcor2.object_types import Generic
from arcor2.services import Service
from arcor2.helpers import camel_case_to_snake_case


TypesDict = Dict[str, Union[Type[Generic], Type[Service]]]


class ParameterPluginException(Arcor2Exception):
    pass


class ParameterPlugin(metaclass=abc.ABCMeta):

    EXACT_TYPE = True

    @classmethod
    @abc.abstractmethod
    def type(cls) -> Any:
        """
        Returns python type.
        """
        pass

    @classmethod
    def type_name(cls) -> str:
        """
        Returns parameter type as string used in JSON.
        """
        return camel_case_to_snake_case(cls.type().__name__)

    @classmethod
    def meta(cls, param_meta: ActionParameterMeta, action_method: Callable, action_node: ast.FunctionDef) -> None:

        assert param_meta.type == cls.type_name()
        assert param_meta.name

    @classmethod
    def parse_id(cls, param: ActionParameter) -> Tuple[str, str, str]:  # TODO does it make sense here?

        try:
            obj_id, ap_id, value_id = json.loads(param.value).split(".")
        except ValueError:
            raise ParameterPluginException(f"Parameter: {param.id} has invalid value: {param.value}.")
        return obj_id, ap_id, value_id

    @classmethod
    @abc.abstractmethod
    # TODO not instances but type_defs
    def value(cls, type_defs: TypesDict, scene: Scene, project: Project, action_id: str, parameter_id: str) -> Any:

        param = project.action(action_id).parameter(parameter_id)
        return json.loads(param.value)
