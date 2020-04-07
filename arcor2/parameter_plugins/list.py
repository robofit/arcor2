import abc
from typing import Any, List, Type
import json


from arcor2.parameter_plugins.base import ParameterPlugin, ParameterPluginException, TypesDict
from arcor2.data.common import Project, Scene, ActionParameter


def get_type_name(base: Type[ParameterPlugin]) -> str:
    return f"{base.type_name()}_array"


class ListParameterPlugin(ParameterPlugin):

    @classmethod
    @abc.abstractmethod
    def value(cls, type_defs: TypesDict, scene: Scene, project: Project, action_id: str, parameter_id: str) \
            -> List[Any]:

        val = super(ListParameterPlugin, cls).value(type_defs, scene, project, action_id, parameter_id)

        if not isinstance(val, list):
            raise ParameterPluginException("Not a list!")
        if val and not isinstance(val[0], cls.type()):
            raise ParameterPluginException("List content does not have expected type!")

        return val

    @classmethod
    def param_value_list(cls, param: ActionParameter) -> List[str]:

        lst = json.loads(param.value)

        if not isinstance(lst, list):
            raise ParameterPluginException("Parameter value should be list of references to action points.")

        return lst
