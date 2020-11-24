import abc
import json
from typing import Any, Callable

import humps
from typed_ast import ast3 as ast

from arcor2.cached import CachedProject as CProject
from arcor2.cached import CachedScene as CScene
from arcor2.data.object_type import ParameterMeta
from arcor2.parameter_plugins import ParameterPluginException, TypesDict


class ParameterPlugin(metaclass=abc.ABCMeta):

    EXACT_TYPE = True
    COUNTABLE = False

    @classmethod
    def _id_from_value(cls, value: str) -> str:

        arbitrary_id = cls._value_from_json(value)

        if not isinstance(arbitrary_id, str):
            raise ParameterPluginException("String expected.")

        return arbitrary_id

    @classmethod
    @abc.abstractmethod
    def type(cls) -> Any:
        """Returns python type."""
        pass

    @classmethod
    def type_name(cls) -> str:
        """Returns parameter type as string used in JSON."""
        return humps.depascalize(cls.type().__name__)

    @classmethod
    def meta(cls, param_meta: ParameterMeta, action_method: Callable, action_node: ast.FunctionDef) -> None:

        assert param_meta.type == cls.type_name()
        assert param_meta.name

    @classmethod
    @abc.abstractmethod
    def parameter_value(
        cls, type_defs: TypesDict, scene: CScene, project: CProject, action_id: str, parameter_id: str
    ) -> Any:

        action = project.action(action_id)
        param_value = action.parameter(parameter_id).value

        try:
            val = cls._value_from_json(param_value)
        except ParameterPluginException as e:
            raise ParameterPluginException(
                f"Parameter {action.name}/{parameter_id} has invalid value: '{param_value}'."
            ) from e

        if not isinstance(val, cls.type()):

            raise ParameterPluginException(f"Parameter {action.name}/{parameter_id} has invalid type: '{type(val)}'.")

        return val

    @classmethod
    def _value_from_json(cls, value: str) -> Any:

        try:
            return json.loads(value)
        except ValueError as e:
            raise ParameterPluginException(f"Invalid value '{value}'.") from e

    @classmethod
    def parameter_execution_value(
        cls, type_defs: TypesDict, scene: CScene, project: CProject, action_id: str, parameter_id: str
    ) -> Any:

        return cls.parameter_value(type_defs, scene, project, action_id, parameter_id)

    @classmethod
    def value_to_json(cls, value: Any) -> str:
        return json.dumps(value)

    @classmethod
    def uses_orientation(cls, project: CProject, action_id: str, parameter_id: str, orientation_id: str) -> bool:
        return False

    @classmethod
    def uses_robot_joints(cls, project: CProject, action_id: str, parameter_id: str, robot_joints_id: str) -> bool:
        return False
