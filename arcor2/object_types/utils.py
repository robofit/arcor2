import copy
import inspect
from dataclasses import dataclass, field
from typing import Dict, Iterator, Optional, Set, Tuple, Type, get_type_hints

import horast

from typed_ast.ast3 import AST

import typing_inspect  # type: ignore

import arcor2
from arcor2.data.common import ActionMetadata
from arcor2.data.object_type import ActionParameterMeta, ObjectAction, ObjectTypeMeta
from arcor2.data.robot import RobotMeta
from arcor2.docstring import parse_docstring
from arcor2.exceptions import Arcor2Exception
from arcor2.object_types.abstract import Generic, GenericWithPose, Robot
from arcor2.parameter_plugins.base import ParameterPlugin, ParameterPluginException
from arcor2.source.utils import find_function

SERVICES_METHOD_NAME = "from_services"


class ObjectTypeException(Arcor2Exception):
    pass


@dataclass
class ObjectTypeData:

    meta: ObjectTypeMeta
    type_def: Optional[Type[Generic]] = None
    actions: Dict[str, ObjectAction] = field(default_factory=dict)
    ast: Optional[AST] = None
    robot_meta: Optional[RobotMeta] = None

    def __post_init__(self):
        if not self.meta.disabled:
            assert self.type_def is not None
            assert self.ast is not None


ObjectTypeDict = Dict[str, ObjectTypeData]


def built_in_types() -> Iterator[Tuple[str, Type[Generic]]]:
    """
    Yields class name and class definition tuple
    """

    for cls in inspect.getmembers(arcor2.object_types.abstract, inspect.isclass):
        if not issubclass(cls[1], Generic):
            continue

        yield cls[0], cls[1]


def get_built_in_type(name: str) -> Type[Generic]:

    for bname, cls in built_in_types():
        if name == bname:
            return cls

    raise KeyError


def built_in_types_names() -> Set[str]:

    names = set()

    for type_name, _ in built_in_types():
        names.add(type_name)

    return names


class DataError(Arcor2Exception):
    pass


def obj_description_from_base(data: ObjectTypeDict, obj_type: ObjectTypeMeta) -> str:

    try:
        obj = data[obj_type.base]
    except KeyError:
        raise DataError(f"Unknown object type: {obj_type}.")

    if obj.meta.description:
        return obj.meta.description

    if not obj.meta.base:
        return ""

    return obj_description_from_base(data, data[obj.meta.base].meta)


def meta_from_def(type_def: Type[Generic], built_in: bool = False) -> ObjectTypeMeta:

    obj = ObjectTypeMeta(type_def.__name__,
                         type_def.description(),
                         built_in=built_in,
                         # TODO kind of hack to make Generic etc. abstract
                         abstract=inspect.isabstract(type_def) or type_def in (Generic, GenericWithPose, Robot),
                         has_pose=issubclass(type_def, GenericWithPose))

    bases = inspect.getmro(type_def)

    if len(bases) > 2:
        obj.base = bases[1].__name__

    return obj


def built_in_types_data(plugins: Dict[Type, Type[ParameterPlugin]]) -> ObjectTypeDict:

    # TODO get built_in_types sources and rather use get_object_actions(source)?

    ret: ObjectTypeDict = {}

    # built-in object types / services
    for _, type_def in built_in_types():

        assert issubclass(type_def, Generic)

        ast = horast.parse(inspect.getsource(type_def))

        d = ObjectTypeData(meta_from_def(type_def, built_in=True),
                           type_def,
                           object_actions(plugins, type_def, ast),
                           ast
                           )

        ret[d.meta.type] = d

    return ret


class IgnoreActionException(Arcor2Exception):
    pass


def resolve_param(plugins: Dict[Type, Type[ParameterPlugin]], name: str, ttype) -> Type[ParameterPlugin]:

    try:
        return plugins[ttype]
    except KeyError:
        for k, v in plugins.items():
            if not v.EXACT_TYPE and inspect.isclass(ttype) and issubclass(ttype, k):
                return v

    # ignore action with unknown parameter type
    raise IgnoreActionException(f"Parameter {name} has unknown type {ttype}.")


def object_actions(plugins: Dict[Type, Type[ParameterPlugin]], type_def: Type[Generic], tree: AST) \
        -> Dict[str, ObjectAction]:

    ret: Dict[str, ObjectAction] = {}

    # ...inspect.ismethod does not work on un-initialized classes
    for method_name, method_def in inspect.getmembers(type_def, predicate=inspect.isfunction):

        # TODO check also if the method has 'action' decorator (ast needed)
        if not hasattr(method_def, "__action__"):
            continue

        # action from ancestor, will be copied later (only if the action was not overridden)
        base_cls_def = type_def.__bases__[0]
        if hasattr(base_cls_def, method_name) and getattr(base_cls_def, method_name) == method_def:
            continue

        meta: ActionMetadata = method_def.__action__

        if not issubclass(type_def, GenericWithPose):
            # actions of object without pose are automatically set as free
            meta.free = True

        data = ObjectAction(name=method_name, meta=meta)

        if method_name in type_def.CANCEL_MAPPING:
            meta.cancellable = True

        doc = parse_docstring(method_def.__doc__)
        doc_short = doc["short_description"]
        if doc_short:
            data.description = doc_short

        signature = inspect.signature(method_def)

        method_tree = find_function(method_name, tree)

        try:

            for name, ttype in get_type_hints(method_def).items():

                if name == "return":

                    # ...just ignore NoneType for returns
                    if ttype == type(None):  # noqa: E721
                        continue

                    if typing_inspect.is_tuple_type(ttype):
                        for arg in typing_inspect.get_args(ttype):
                            resolved_param = resolve_param(plugins, name, arg)
                            if resolved_param is None:
                                raise IgnoreActionException("None in return tuple is not supported.")
                            data.returns.append(resolved_param.type_name())
                    else:
                        # TODO resolving needed for e.g. enums - add possible values to action metadata somewhere?
                        data.returns = [resolve_param(plugins, name, ttype).type_name()]

                    continue

                param_type = resolve_param(plugins, name, ttype)

                assert param_type is not None

                args = ActionParameterMeta(name=name, type=param_type.type_name())
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
                    args.default_value = def_val

                try:
                    args.description = doc["params"][name].strip()
                except KeyError:
                    pass

                data.parameters.append(args)

        except IgnoreActionException as e:
            data.disabled = True
            data.problem = e.message
            # TODO log exception

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
