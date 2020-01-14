from typing import Dict, Type
import inspect

# TODO just temporary solution
from arcor2.parameter_plugins.base import ParameterPlugin
from arcor2.parameter_plugins.double import DoublePlugin
from arcor2.parameter_plugins.integer import IntegerPlugin
from arcor2.parameter_plugins.integer_enum import IntegerEnumPlugin
from arcor2.parameter_plugins.joints import JointsPlugin
from arcor2.parameter_plugins.pose import PosePlugin
from arcor2.parameter_plugins.relative_pose import RelativePosePlugin
from arcor2.parameter_plugins.string import StringPlugin
from arcor2.parameter_plugins.string_enum import StringEnumPlugin

PARAM_PLUGINS: Dict[str, Type[ParameterPlugin]] = {}

# TODO temporary solution
PLUGINS = [DoublePlugin, IntegerPlugin, IntegerEnumPlugin, JointsPlugin, PosePlugin, RelativePosePlugin,
           StringPlugin, StringEnumPlugin]
TYPE_TO_PLUGIN: Dict[Type, Type[ParameterPlugin]] = {}

for plug in PLUGINS:
    assert not inspect.isabstract(plug)
    if plug.type_name() in PARAM_PLUGINS:
        print(f"Plugin for type {plug.type_name()} already registered.")
        continue
    # TODO figure out why mypy complains
    # Only concrete class can be given where "Type[ParameterPlugin]" is expected
    PARAM_PLUGINS[plug.type_name()] = plug  # type: ignore
    TYPE_TO_PLUGIN[plug.type()] = plug  # type: ignore
