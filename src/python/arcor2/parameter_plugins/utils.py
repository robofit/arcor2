import inspect
from typing import Any, Dict, Set, Type

from arcor2.parameter_plugins import ParameterPluginException
from arcor2.parameter_plugins.base import ParameterPlugin

_plugins: Set[Type[ParameterPlugin]] = set()
_type_name_to_plugin: Dict[str, Type[ParameterPlugin]] = {}
_type_to_plugin: Dict[Type, Type[ParameterPlugin]] = {}


def load_plugins() -> None:

    # TODO just temporary solution - allow loading plugins based on env. var

    from arcor2.parameter_plugins.boolean import BooleanListPlugin, BooleanPlugin
    from arcor2.parameter_plugins.double import DoubleListPlugin, DoublePlugin
    from arcor2.parameter_plugins.image import ImagePlugin
    from arcor2.parameter_plugins.integer import IntegerListPlugin, IntegerPlugin
    from arcor2.parameter_plugins.integer_enum import IntegerEnumPlugin
    from arcor2.parameter_plugins.joints import JointsPlugin
    from arcor2.parameter_plugins.pose import PoseListPlugin, PosePlugin
    from arcor2.parameter_plugins.relative_pose import RelativePosePlugin
    from arcor2.parameter_plugins.string import StringListPlugin, StringPlugin
    from arcor2.parameter_plugins.string_enum import StringEnumPlugin

    _plugins.update(
        {
            BooleanPlugin,
            BooleanListPlugin,
            DoublePlugin,
            DoubleListPlugin,
            ImagePlugin,
            IntegerPlugin,
            IntegerListPlugin,
            IntegerEnumPlugin,
            JointsPlugin,
            PosePlugin,
            PoseListPlugin,
            RelativePosePlugin,
            StringPlugin,
            StringListPlugin,
            StringEnumPlugin,
        }
    )

    _type_name_to_plugin.clear()
    _type_to_plugin.clear()

    for plug in _plugins:
        if plug.type_name() in _type_name_to_plugin:
            print(f"Plugin for type {plug.type_name()} already registered.")
            continue

        _type_name_to_plugin[plug.type_name()] = plug
        _type_to_plugin[plug.type()] = plug


def known_parameter_types() -> Set[str]:

    return set(_type_name_to_plugin.keys())


def plugin_from_instance(inst: Any) -> Type[ParameterPlugin]:

    for plugin in _plugins:
        if isinstance(inst, plugin.type()):
            return plugin
    raise ParameterPluginException(f"Plugin for type {type(inst)} was not found.")


def plugin_from_type_name(param_type_name: str) -> Type[ParameterPlugin]:

    try:
        return _type_name_to_plugin[param_type_name]
    except KeyError:
        raise ParameterPluginException(f"Unknown parameter type {param_type_name}.")


def plugin_from_type(param_type: Type[Any]) -> Type[ParameterPlugin]:

    try:
        return _type_to_plugin[param_type]
    except KeyError:

        for k, v in _type_to_plugin.items():
            if not v.EXACT_TYPE and inspect.isclass(param_type) and issubclass(param_type, k):
                return v

    try:
        raise ParameterPluginException(f"Unknown parameter type {param_type.__name__}.")
    except AttributeError:
        raise ParameterPluginException(f"Unknown parameter type {param_type}.")


load_plugins()
