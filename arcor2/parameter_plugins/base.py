import abc
import json
from typing import Any, Callable, Dict, Type

from typed_ast import ast3 as ast

from arcor2.cached import CachedProject, CachedScene
from arcor2.data.common import ActionParameter
from arcor2.data.object_type import ActionParameterMeta
from arcor2.exceptions import Arcor2Exception
from arcor2.helpers import camel_case_to_snake_case
from arcor2.object_types.abstract import Generic

TypesDict = Dict[str, Type[Generic]]


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
    def param_value(cls, param: ActionParameter) -> str:

        # TODO support for link, constant (will need access to project)
        assert param.value is not None

        try:
            ret = json.loads(param.value)
        except ValueError:
            raise ParameterPluginException(f"Parameter: {param.id} has invalid value: {param.value}.")

        if not isinstance(ret, str):
            raise ParameterPluginException(f"Parameter: {param.id} has invalid value (string expected): {param.value}.")

        return ret

    @classmethod
    @abc.abstractmethod
    # TODO not instances but type_defs
    def value(cls, type_defs: TypesDict, scene: CachedScene, project: CachedProject, action_id: str, parameter_id: str)\
            -> Any:

        param = project.action(action_id).parameter(parameter_id)
        try:
            return json.loads(param.value)
        except json.decoder.JSONDecodeError as e:
            raise ParameterPluginException(f"Value of {action_id}/{parameter_id} is not a valid JSON.", e)

    @classmethod
    def execution_value(cls, type_defs: TypesDict, scene: CachedScene, project: CachedProject, action_id: str,
                        parameter_id: str) -> Any:

        return cls.value(type_defs, scene, project, action_id, parameter_id)

    @classmethod
    def value_to_json(cls, value: Any) -> str:
        return json.dumps(value)

    @classmethod
    def uses_orientation(cls, project: CachedProject, action_id: str, parameter_id: str, orientation_id: str) -> bool:
        return False

    @classmethod
    def uses_robot_joints(cls, project: CachedProject, action_id: str, parameter_id: str, robot_joints_id: str) -> bool:
        return False
