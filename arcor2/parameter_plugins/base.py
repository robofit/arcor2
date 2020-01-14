import abc
from typing import Callable, Tuple, Any, Dict, Union, Type

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
    def meta(cls, param_meta: ActionParameterMeta, action_method: Callable, source: str) -> None:

        assert param_meta.type == cls.type_name()
        assert param_meta.name

    @classmethod
    def parse_id(cls, param: ActionParameter) -> Tuple[str, str, str]:  # TODO does it make sense here?

        if not isinstance(param.value, str):
            raise ParameterPluginException(f"Cannot parse non-str parameter {param.id}.")

        try:
            obj_id, ap_id, value_id = param.value.split(".")
        except ValueError:
            raise ParameterPluginException(f"Parameter: {param.id} has invalid value: {param.value}.")
        return obj_id, ap_id, value_id

    @classmethod
    @abc.abstractmethod
    # TODO not instances but type_defs
    def value(cls, type_defs: TypesDict, scene: Scene, project: Project, action_id: str, parameter_id: str) -> Any:

        param = project.action(action_id).parameter(parameter_id)

        try:
            return cls.type()(param.value)
        except ValueError:
            raise ParameterPluginException(f"Parameter {parameter_id} of action {action_id} has invalid param value: "
                                           f"'{param.value}' (should be of type {cls.type().__name__}).")
