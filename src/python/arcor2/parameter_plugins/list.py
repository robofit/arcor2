import abc
from typing import Any

from arcor2 import json
from arcor2.cached import CachedProject as CProject
from arcor2.cached import CachedScene as CScene
from arcor2.data.common import ActionParameter
from arcor2.parameter_plugins.base import ParameterPlugin, ParameterPluginException, TypesDict


def get_type_name(base: type[ParameterPlugin]) -> str:
    return f"{base.type_name()}_array"


class ListParameterPlugin(ParameterPlugin):
    @classmethod
    @abc.abstractmethod
    def parameter_value(
        cls, type_defs: TypesDict, scene: CScene, project: CProject, action_id: str, parameter_id: str
    ) -> list[Any]:

        val = super(ListParameterPlugin, cls).parameter_value(type_defs, scene, project, action_id, parameter_id)

        if not isinstance(val, list):
            raise ParameterPluginException("Not a list!")
        if val and not isinstance(val[0], cls.type()):
            raise ParameterPluginException("List content does not have expected type!")

        return val

    @classmethod
    def _param_value_list(cls, param: ActionParameter) -> list[str]:

        lst = json.loads(param.value)

        if not isinstance(lst, list):
            raise ParameterPluginException("Parameter value should be list of references to action points.")

        return lst
