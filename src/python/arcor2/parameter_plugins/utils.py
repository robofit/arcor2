import inspect
from typing import Any

from arcor2.parameter_plugins import ParameterPluginException
from arcor2.parameter_plugins.base import ParameterPlugin

TypeToPluginDict = dict[type, type[ParameterPlugin]]

_type_name_to_plugin: dict[str, type[ParameterPlugin]] = {}
_type_to_plugin: TypeToPluginDict = {}


def load_plugins() -> None:

    if _type_name_to_plugin:
        return

    # TODO just temporary solution - allow loading plugins based on env. var

    from arcor2.parameter_plugins.boolean import BooleanPlugin
    from arcor2.parameter_plugins.double import DoublePlugin
    from arcor2.parameter_plugins.image import ImagePlugin
    from arcor2.parameter_plugins.integer import IntegerPlugin
    from arcor2.parameter_plugins.integer_enum import IntegerEnumPlugin
    from arcor2.parameter_plugins.joints import JointsPlugin
    from arcor2.parameter_plugins.pose import PosePlugin
    from arcor2.parameter_plugins.position import PositionPlugin
    from arcor2.parameter_plugins.string import StringPlugin
    from arcor2.parameter_plugins.string_enum import StringEnumPlugin

    plugins: set[type[ParameterPlugin]] = {
        BooleanPlugin,
        # BooleanListPlugin,
        DoublePlugin,
        # DoubleListPlugin,
        ImagePlugin,
        IntegerPlugin,
        # IntegerListPlugin,
        IntegerEnumPlugin,
        JointsPlugin,
        PosePlugin,
        PositionPlugin,
        # PoseListPlugin,
        StringPlugin,
        # StringListPlugin,
        StringEnumPlugin,
    }

    for plug in plugins:
        if plug.type_name() in _type_name_to_plugin:
            print(f"Plugin for type {plug.type_name()} already registered.")
            continue

        _type_name_to_plugin[plug.type_name()] = plug
        _type_to_plugin[plug.type()] = plug


def non_exact_types() -> TypeToPluginDict:
    return {k: v for k, v in _type_to_plugin.items() if not v.EXACT_TYPE}


def known_parameter_types() -> set[str]:

    return set(_type_name_to_plugin.keys())


def plugin_from_instance(inst: Any) -> type[ParameterPlugin]:

    # TODO support for lists (e.g. list[Pose])
    return plugin_from_type(type(inst))


def plugin_from_type_name(param_type_name: str) -> type[ParameterPlugin]:

    try:
        return _type_name_to_plugin[param_type_name]
    except KeyError:
        raise ParameterPluginException(f"Unknown parameter type {param_type_name}.")


def plugin_from_type(param_type: type[Any]) -> type[ParameterPlugin]:

    try:
        return _type_to_plugin[param_type]
    except KeyError:

        try:
            type_name = param_type.__name__
        except AttributeError:
            type_name = str(param_type)

        plugin: None | type[ParameterPlugin] = None
        for k, v in non_exact_types().items():
            if inspect.isclass(param_type) and issubclass(param_type, k):
                if plugin is not None:
                    raise ParameterPluginException(f"There is more than one plugin that matches type {type_name}.")
                plugin = v
        if plugin:
            return plugin

    raise ParameterPluginException(f"Unknown parameter type {type_name}.")


load_plugins()
