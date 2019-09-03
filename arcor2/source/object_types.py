from typing import Dict

from horast import parse  # type: ignore  # TODO remove when version with py.typed on pypi
from typed_ast.ast3 import Assign, Attribute, FunctionDef, Name, ClassDef, Call, keyword, NameConstant, Str, Module

from arcor2.data.common import ObjectActions, ActionMetadata, ObjectAction, ObjectActionArgs, ObjectTypeMeta
from arcor2.helpers import camel_case_to_snake_case
from arcor2.source import SourceException


def get_object_actions(object_source: str) -> ObjectActions:

    tree = object_cls_def(object_source)

    action_attr: Dict[str, ActionMetadata] = {}
    ret: ObjectActions = []

    for node in tree.body:
        if not isinstance(node, Assign):
            continue

        if not hasattr(node, "targets"):
            continue

        if not len(node.targets) == 1 or not isinstance(node.targets[0], Attribute):
            continue

        if node.targets[0].attr != "__action__":
            continue

        # TODO further checks?
        meta = ActionMetadata()

        assert isinstance(node.value, Call)

        for kwarg in node.value.keywords:

            assert isinstance(kwarg, keyword)

            if not kwarg.arg:
                continue

            try:
                assert isinstance(kwarg.value, NameConstant)
                setattr(meta, kwarg.arg, kwarg.value.value)
            except AttributeError:
                raise SourceException(f"Unknown __action__ attribute {kwarg.arg}.")
        assert isinstance(node.targets[0].value, Name)
        action_attr[node.targets[0].value.id] = meta

    # TODO add missing attributes (e.g. free, composite, blackbox) to action_attr?

    for node in tree.body:

        if not isinstance(node, FunctionDef):
            continue

        for decorator in node.decorator_list:
            assert isinstance(decorator, Name)
            if decorator.id == "action":
                break
        else:
            if node.name in action_attr:
                raise SourceException(f"Method {node.name} has metadata, but no @action decorator.")
            continue

        if node.name not in action_attr:
            raise SourceException(f"Method {node.name} has @action decorator, but no metadata.")

        oa = ObjectAction(name=node.name, meta=action_attr[node.name])

        for aarg in node.args.args:

            if aarg.arg == "self":
                continue

            if aarg.annotation is None:
                raise SourceException(f"Argument {aarg.arg} of method {node.name} not annotated.")

            assert isinstance(aarg.annotation, Name)
            oa.action_args.append(ObjectActionArgs(name=aarg.arg, type=aarg.annotation.id))

        ret.append(oa)

    return ret


def check_object_type(object_type_source: str) -> None:
    """
    Checks whether the object type source is a valid one.
    :param object_type_source:
    :return:
    """

    object_type_meta(object_type_source)
    get_object_actions(object_type_source)


def object_type_meta(object_source: str) -> ObjectTypeMeta:

    tree = object_cls_def(object_source)

    if len(tree.bases) > 1:
        raise SourceException("Only one base class is supported!")

    obj = ObjectTypeMeta(tree.name)

    if tree.bases:
        assert isinstance(tree.bases[0], Name)
        obj.base = tree.bases[0].id

    for node in tree.body:
        if not isinstance(node, Assign):
            continue
        if len(node.targets) == 1 and isinstance(node.targets[0], Name) and node.targets[0].id == "__DESCRIPTION__":
            assert isinstance(node.value, Str)
            obj.description = node.value.s

    return obj


def object_cls_def(object_source: str) -> ClassDef:

    tree = parse(object_source)  # TODO figure out if parse is correctly annotated

    assert isinstance(tree, Module)

    cls_def = None

    for node in tree.body:

        if isinstance(node, ClassDef):
            if cls_def is None:
                cls_def = node
                break
            else:
                raise SourceException("Multiple class definition!")
    else:
        raise SourceException("No class definition!")

    return cls_def


def fix_object_name(object_id: str) -> str:

    return camel_case_to_snake_case(object_id).replace(' ', '_')
