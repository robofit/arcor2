import copy
import inspect
import os
from ast import AST
from typing import get_type_hints

import humps
import typing_inspect
from dataclasses_jsonschema import JsonSchemaMixin

from arcor2 import helpers as hlp
from arcor2.data.common import ActionMetadata
from arcor2.data.object_type import ParameterMeta
from arcor2.docstring import parse_docstring
from arcor2.exceptions import Arcor2Exception
from arcor2.object_types.abstract import Generic, GenericWithPose
from arcor2.object_types.utils import built_in_types, get_settings_def, iterate_over_actions
from arcor2.parameter_plugins import ParameterPluginException
from arcor2.parameter_plugins.utils import plugin_from_type
from arcor2.source.utils import SourceException, find_function, parse_def
from arcor2_arserver import logger, settings
from arcor2_arserver.object_types.data import ObjectTypeData, ObjectTypeDict
from arcor2_arserver_data.objects import ObjectAction, ObjectTypeMeta


class ObjectTypeException(Arcor2Exception):
    pass


async def remove_object_type(obj_type_id: str) -> None:

    path = os.path.join(settings.OBJECT_TYPE_PATH, settings.OBJECT_TYPE_MODULE, f"{humps.depascalize(obj_type_id)}.py")
    logger.debug(f"Deleting {path}.")

    try:
        await hlp.run_in_executor(os.remove, path, propagate=[FileNotFoundError])
    except FileNotFoundError as e:
        raise Arcor2Exception(f"File for {obj_type_id} was not found.") from e


def obj_description_from_base(data: ObjectTypeDict, obj_type: ObjectTypeMeta) -> str:

    try:
        obj = data[obj_type.base]
    except KeyError:
        raise Arcor2Exception(f"Unknown object type: {obj_type}.")

    if obj.meta.description:
        return obj.meta.description

    if not obj.meta.base:
        return ""

    return obj_description_from_base(data, data[obj.meta.base].meta)


def get_dataclass_params(type_def: type[JsonSchemaMixin]) -> list[ParameterMeta]:
    """Analyzes properties of dataclass and returns their metadata.

    :param type_def:
    :return:
    """

    ret: list[ParameterMeta] = []

    sig = inspect.signature(type_def.__init__)

    # TODO Will this work for inherited properties? Make a test! There is also dataclasses.fields maybe...
    # TODO use inspect.signature to get reliable order of parameters
    for name, ttype in get_type_hints(type_def.__init__).items():
        if name == "return":
            continue

        if issubclass(ttype, JsonSchemaMixin):
            pass
            # TODO disabled as it is anyway not supported by AREditor
            # pm = ParameterMeta(name=name, type="dataclass")  # TODO come-up with plugin for this?
            # pm.children = get_dataclass_params(ttype)
        else:
            param_type = plugin_from_type(ttype)
            assert param_type is not None
            pm = ParameterMeta(name=name, type=param_type.type_name())

            def_val = sig.parameters[name].default
            if def_val is not inspect.Parameter.empty:
                pm.default_value = param_type.value_to_json(def_val)

            # TODO description, ranges, etc.

        ret.append(pm)

    return ret


def meta_from_def(type_def: type[Generic], built_in: bool = False) -> ObjectTypeMeta:

    obj = ObjectTypeMeta(
        type_def.__name__,
        type_def.description(),
        built_in=built_in,
        abstract=type_def.abstract(),
        has_pose=issubclass(type_def, GenericWithPose),
    )

    for base in inspect.getmro(type_def)[1:-1]:  # skip type itself (first base) and the last one (object)
        if issubclass(base, Generic):
            obj.base = base.__name__
            break

    obj.settings = get_dataclass_params(get_settings_def(type_def))

    return obj


def built_in_types_data() -> ObjectTypeDict:

    ret: ObjectTypeDict = {}

    # built-in object types / services
    for _, type_def in built_in_types():

        assert issubclass(type_def, Generic)

        ast = parse_def(type_def)

        d = ObjectTypeData(meta_from_def(type_def, built_in=True), type_def, object_actions(type_def, ast), ast)

        ret[d.meta.type] = d

    return ret


class IgnoreActionException(Arcor2Exception):
    pass


def object_actions(type_def: type[Generic], tree: AST) -> dict[str, ObjectAction]:

    ret: dict[str, ObjectAction] = {}

    # ...inspect.ismethod does not work on un-initialized classes
    for method_name, method_def in iterate_over_actions(type_def):

        meta: ActionMetadata = method_def.__action__  # type: ignore

        if meta.hidden:
            logger.debug(f"Action {method_name} of {type_def.__name__} is hidden.")
            continue

        data = ObjectAction(name=method_name, meta=meta)

        if method_name in type_def.CANCEL_MAPPING:
            meta.cancellable = True

        try:

            docstring = parse_docstring(method_def.__doc__)
            data.description = docstring.short_description

            signature = inspect.signature(method_def)  # sig.parameters is OrderedDict

            try:
                method_tree = find_function(method_name, tree)
            except SourceException:
                # function is probably defined in predecessor, will be added later
                continue

            hints = get_type_hints(method_def)  # standard (unordered) dict

            if "an" not in signature.parameters.keys():
                raise IgnoreActionException("Action is missing 'an' parameter.")

            try:
                if hints["an"] != str | None:  # noqa:E711
                    raise IgnoreActionException("Parameter 'an' has invalid type annotation.")
            except KeyError:
                raise IgnoreActionException("Parameter 'an' is missing type annotation.")

            parameter_names_without_self = list(signature.parameters.keys())[1:]

            if not parameter_names_without_self or parameter_names_without_self[-1] != "an":
                raise IgnoreActionException("The 'an' parameter have to be the last one.")

            # handle return
            try:
                return_ttype = hints["return"]
            except KeyError:
                raise IgnoreActionException("Action is missing return type annotation.")

            # ...just ignore NoneType for returns
            if return_ttype != type(None):  # noqa: E721

                if typing_inspect.is_tuple_type(return_ttype):
                    for arg in typing_inspect.get_args(return_ttype):
                        resolved_param = plugin_from_type(arg)
                        if resolved_param is None:
                            raise IgnoreActionException("None in return tuple is not supported.")
                        data.returns.append(resolved_param.type_name())
                else:
                    # TODO resolving needed for e.g. enums - add possible values to action metadata somewhere?
                    data.returns = [plugin_from_type(return_ttype).type_name()]

            for name in parameter_names_without_self[:-1]:  # omit also an

                try:
                    ttype = hints[name]
                except KeyError:
                    raise IgnoreActionException(f"Parameter {name} is missing type annotation.")

                param_type = plugin_from_type(ttype)

                assert param_type is not None

                args = ParameterMeta(name=name, type=param_type.type_name())
                try:
                    param_type.meta(args, method_def, method_tree)
                except ParameterPluginException as e:
                    raise IgnoreActionException(e) from e

                if name in type_def.DYNAMIC_PARAMS:
                    args.dynamic_value = True
                    dvp = type_def.DYNAMIC_PARAMS[name][1]
                    if dvp:
                        args.dynamic_value_parents = dvp

                def_val = signature.parameters[name].default
                if def_val is not inspect.Parameter.empty:
                    args.default_value = param_type.value_to_json(def_val)

                args.description = docstring.param(name)
                data.parameters.append(args)

        except Arcor2Exception as e:
            data.disabled = True
            data.problem = str(e)
            logger.warn(f"Disabling action {method_name} of {type_def.__name__}. {str(e)}")

        ret[data.name] = data

    return ret


def add_ancestor_actions(obj_type_name: str, object_types: ObjectTypeDict) -> None:

    base_name = object_types[obj_type_name].meta.base

    if not base_name:
        return

    if object_types[base_name].meta.base:
        add_ancestor_actions(base_name, object_types)

    # do not add action from base if it is overridden in child
    # TODO rewrite (use adv. of dict!)
    for base_action in object_types[base_name].actions.values():
        for obj_action in object_types[obj_type_name].actions.values():
            if base_action.name == obj_action.name:

                # built-in object has no "origins" yet
                if not obj_action.origins:
                    obj_action.origins = base_name
                break
        else:
            action = copy.deepcopy(base_action)
            if not action.origins:
                action.origins = base_name
            object_types[obj_type_name].actions[action.name] = action


__all__ = [
    ObjectTypeException.__name__,
    ObjectTypeData.__name__,
    "ObjectTypeDict",
    meta_from_def.__name__,
    built_in_types_data.__name__,
    object_actions.__name__,
    add_ancestor_actions.__name__,
]
