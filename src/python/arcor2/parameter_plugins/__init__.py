from typing import Dict, Set, Type

# TODO just temporary solution - allow loading plugins based on env. var or from project service?
from arcor2.parameter_plugins.base import ParameterPlugin
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

Plugins = Dict[Type, Type[ParameterPlugin]]

PLUGINS: Set[Type[ParameterPlugin]] = {
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

PARAM_PLUGINS: Dict[str, Type[ParameterPlugin]] = {}
TYPE_TO_PLUGIN: Plugins = {}

for plug in PLUGINS:
    if plug.type_name() in PARAM_PLUGINS:
        print(f"Plugin for type {plug.type_name()} already registered.")
        continue
    # TODO figure out why mypy complains
    # Only concrete class can be given where "Type[ParameterPlugin]" is expected
    PARAM_PLUGINS[plug.type_name()] = plug  # type: ignore
    TYPE_TO_PLUGIN[plug.type()] = plug  # type: ignore
