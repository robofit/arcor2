import abc
from typing import Any, List, Type, Iterator, Tuple
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
    def parse_list_id(cls, param: ActionParameter) -> Iterator[Tuple[str, str, str]]:

        lst = json.loads(param.value)

        if not isinstance(lst, list):
            raise ParameterPluginException("Parameter value should be list of references to action points.")

        for val in lst:
            try:
                obj_id, ap_id, value_id = val.split(".")
            except ValueError:
                raise ParameterPluginException(f"Parameter: {param.id} has invalid value: {param.value}.")
            yield obj_id, ap_id, value_id
