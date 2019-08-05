import copy
import inspect
from typing import Dict, Iterator, Tuple, Type, Set, get_type_hints

from undecorated import undecorated  # type: ignore

import arcor2
from arcor2.data import ObjectTypeMeta, ObjectTypeMetaDict, ObjectActionsDict, ObjectAction, ObjectActionArgs
from arcor2.exceptions import Arcor2Exception
from arcor2.object_types import Generic


def built_in_types() -> Iterator[Tuple[str, Type[Generic]]]:
    """
    Yields class name and class definition tuple
    """

    for cls in inspect.getmembers(arcor2.object_types, inspect.isclass):
        if not issubclass(cls[1], Generic):
            continue

        yield cls[0], cls[1]


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

        obj = ObjectTypeMeta(type_name, type_def.__DESCRIPTION__, True)

        bases = inspect.getmro(type_def)

        assert 1 < len(bases) < 4

        if len(bases) == 3:
            obj.base = bases[1].__name__

        d[type_name] = obj

    return d


def built_in_types_actions() -> ObjectActionsDict:

    # TODO get built_in_types sources and rather use get_object_actions(source)?

    d: ObjectActionsDict = {}

    # built-in object types
    for type_name, type_def in built_in_types():

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
            undecorated_method = undecorated(method[1])

            for name, ttype in get_type_hints(undecorated_method).items():

                try:
                    if name == "return":
                        data.returns = ttype.__name__
                        continue

                    data.action_args.append(ObjectActionArgs(name=name, type=ttype.__name__))

                except AttributeError:
                    print(f"Skipping {ttype}")  # TODO make a fix for Union

            if type_name not in d:
                d[type_name] = []
            d[type_name].append(data)

    return d


def add_ancestor_actions(obj_type: str, object_actions: ObjectActionsDict, object_types: ObjectTypeMetaDict) -> None:

    base_name = object_types[obj_type].base

    if not base_name:
        return

    if object_types[base_name].base:
        add_ancestor_actions(base_name, object_actions, object_types)

    # do not add action from base if it is overridden in child
    for base_action in object_actions[base_name]:
        for obj_action in object_actions[obj_type]:
            if base_action.name == obj_action.name:

                # built-in object has no "origins" yet
                if not obj_action.origins:
                    obj_action.origins = base_name
                break
        else:
            action = copy.deepcopy(base_action)
            if not action.origins:
                action.origins = base_name
            object_actions[obj_type].append(action)
