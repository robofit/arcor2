from typing import Dict, Type, Set
import inspect
import pkgutil
import importlib

# TODO just temporary solution - allow loading plugins based on env. var or from project service?
from arcor2 import parameter_plugins
from arcor2.parameter_plugins.base import ParameterPlugin

PARAM_PLUGINS: Dict[str, Type[ParameterPlugin]] = {}

PLUGINS: Set[Type[ParameterPlugin]] = set()

for _, module_name, _ in pkgutil.iter_modules(parameter_plugins.__path__):  # type: ignore

    module = importlib.import_module(f"arcor2.parameter_plugins.{module_name}")

    for name, obj in inspect.getmembers(module):
        if not inspect.isclass(obj) or inspect.isabstract(obj) or not issubclass(obj, ParameterPlugin):
            continue
        PLUGINS.add(obj)


TYPE_TO_PLUGIN: Dict[Type, Type[ParameterPlugin]] = {}

for plug in PLUGINS:
    if plug.type_name() in PARAM_PLUGINS:
        print(f"Plugin for type {plug.type_name()} already registered.")
        continue
    # TODO figure out why mypy complains
    # Only concrete class can be given where "Type[ParameterPlugin]" is expected
    PARAM_PLUGINS[plug.type_name()] = plug  # type: ignore
    TYPE_TO_PLUGIN[plug.type()] = plug  # type: ignore
