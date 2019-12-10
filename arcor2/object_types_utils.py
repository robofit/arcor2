import copy
import inspect
from typing import Dict, Iterator, Tuple, Type, Set, get_type_hints, Union, Optional

import arcor2
from arcor2.data.object_type import ObjectTypeMetaDict, ObjectActionsDict, ObjectTypeMeta, ObjectActionArg, \
    ObjectAction, ObjectActions
from arcor2.data.common import ActionParameterTypeEnum, StrEnum, IntEnum, PARAM_TO_TYPE
from arcor2.exceptions import Arcor2Exception
from arcor2.object_types import Generic
from arcor2.services import Service
from arcor2.docstring import parse_docstring

SERVICES_METHOD_NAME = "from_services"


class ObjectTypeException(Arcor2Exception):
    pass


PARAM_MAPPING: Dict[str, ActionParameterTypeEnum] = {k.__name__: v for k, v in PARAM_TO_TYPE.inverse.items()}


def built_in_types() -> Iterator[Tuple[str, Type[Generic]]]:
    """
    Yields class name and class definition tuple
    """

    for cls in inspect.getmembers(arcor2.object_types, inspect.isclass):
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


def obj_description_from_base(data: Dict[str, ObjectTypeMeta], obj_type: ObjectTypeMeta) -> str:

    try:
        obj = data[obj_type.base]
    except KeyError:
        raise DataError(f"Unknown object type: {obj_type}.")

    if obj.description:
        return obj.description

    if not obj.base:
        return ""

    return obj_description_from_base(data, data[obj.base])


def built_in_types_meta() -> ObjectTypeMetaDict:

    d: ObjectTypeMetaDict = {}

    # built-in object types
    for type_name, type_def in built_in_types():
        d[type_name] = meta_from_def(type_def, built_in=True)

    return d


def meta_from_def(type_def: Type[Generic], built_in: bool = False) -> ObjectTypeMeta:

    obj = ObjectTypeMeta(type_def.__name__,
                         type_def.description(),
                         built_in=built_in,
                         # TODO kind of hack to make Generic abstract
                         abstract=inspect.isabstract(type_def) or type_def == Generic)

    bases = inspect.getmro(type_def)

    if len(bases) > 2:
        obj.base = bases[1].__name__

    if hasattr(type_def, SERVICES_METHOD_NAME):

        srv_method = getattr(type_def, SERVICES_METHOD_NAME)

        if not inspect.isfunction(srv_method):
            raise ObjectTypeException(f"{SERVICES_METHOD_NAME} should be method.")

        for name, ttype in get_type_hints(srv_method).items():
            if name == "return":
                continue
            obj.needs_services.add(ttype.__name__)

    # TODO check whether the same services are also in constructor

    return obj


def built_in_types_actions() -> ObjectActionsDict:

    # TODO get built_in_types sources and rather use get_object_actions(source)?

    d: ObjectActionsDict = {}

    # built-in object types
    for type_name, type_def in built_in_types():

        if type_name not in d:
            d[type_name] = []
        d[type_name] = object_actions(type_def)

    return d


def object_actions(type_def: Union[Type[Generic], Type[Service]]) -> ObjectActions:

    ret: ObjectActions = []

    # ...inspect.ismethod does not work on un-initialized classes
    for method in inspect.getmembers(type_def, predicate=inspect.isfunction):

        # TODO check also if the method has 'action' decorator (ast needed)
        if not hasattr(method[1], "__action__"):
            continue

        meta = method[1].__action__

        data = ObjectAction(name=method[0], meta=meta)

        """
        Methods supposed to be actions have @action decorator, which has to be stripped away in order to get
        method's arguments / type hints.
        """

        doc = parse_docstring(method[1].__doc__)
        data.description = doc["short_description"]

        for name, ttype in get_type_hints(method[1]).items():

            try:
                if name == "return":
                    data.returns = ttype.__name__  # TODO define enum for this
                    continue

                string_allowed_values: Optional[Set[str]] = None
                integer_allowed_values: Optional[Set[int]] = None

                if issubclass(ttype, StrEnum):
                    param_type = ActionParameterTypeEnum.STRING_ENUM
                    string_allowed_values = ttype.set()
                elif issubclass(ttype, IntEnum):
                    param_type = ActionParameterTypeEnum.INTEGER_ENUM
                    integer_allowed_values = ttype.set()
                else:
                    try:
                        param_type = PARAM_MAPPING[ttype.__name__]
                    except KeyError:
                        raise ObjectTypeException(f"Object type {type_def.__name__}, action {method[0]}, "
                                                  f"invalid parameter type: {ttype.__name__}.")

                args = ObjectActionArg(name=name, type=param_type)

                if name in type_def.DYNAMIC_PARAMS:
                    args.dynamic_value = True
                    args.dynamic_value_parents = type_def.DYNAMIC_PARAMS[name][1]

                args.string_allowed_values = string_allowed_values
                args.integer_allowed_values = integer_allowed_values

                try:
                    args.description = doc["params"][name].strip()
                except KeyError:
                    pass

                data.action_args.append(args)

            except AttributeError:
                print(f"Skipping {ttype}")  # TODO make a fix for Union

        ret.append(data)

    return ret


def add_ancestor_actions(obj_type_name: str,
                         object_actions: ObjectActionsDict,
                         object_types: ObjectTypeMetaDict) -> None:

    base_name = object_types[obj_type_name].base

    if not base_name:
        return

    if object_types[base_name].base:
        add_ancestor_actions(base_name, object_actions, object_types)

    # do not add action from base if it is overridden in child
    for base_action in object_actions[base_name]:
        for obj_action in object_actions[obj_type_name]:
            if base_action.name == obj_action.name:

                # built-in object has no "origins" yet
                if not obj_action.origins:
                    obj_action.origins = base_name
                break
        else:
            action = copy.deepcopy(base_action)
            if not action.origins:
                action.origins = base_name
            object_actions[obj_type_name].append(action)
