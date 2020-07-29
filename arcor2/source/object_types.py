import inspect
import os
from typing import Type

import horast

from typed_ast.ast3 import AST, AnnAssign, Assign, ClassDef, ImportFrom, Index, Load, Module, Name, NameConstant,\
    Pass, Store, Str, Subscript, alias

import arcor2.object_types
from arcor2.data.object_type import ObjectTypeMeta
from arcor2.helpers import camel_case_to_snake_case
from arcor2.object_types.abstract import Generic
from arcor2.object_types.utils import built_in_types_names, meta_from_def, object_actions
from arcor2.parameter_plugins import TYPE_TO_PLUGIN
from arcor2.source.utils import find_function, get_name, get_name_attr


def prepare_object_types_dir(path: str, module: str) -> None:

    full_path = os.path.join(path, module)

    if not os.path.exists(full_path):
        os.makedirs(full_path)

    open(os.path.join(full_path, "__init__.py"), "w").close()


def check_object_type(type_def: Type[Generic]) -> None:
    """
    Checks whether the object type source is a valid one.
    :param object_type_source:
    :return:
    """

    meta_from_def(type_def, False)
    object_actions(TYPE_TO_PLUGIN, type_def, horast.parse(inspect.getsource(type_def)))


def fix_object_name(object_id: str) -> str:

    return camel_case_to_snake_case(object_id).replace(' ', '_')


# TODO could this be done like this https://stackoverflow.com/a/9269964/3142796 ??
def new_object_type(parent: ObjectTypeMeta, child: ObjectTypeMeta) -> AST:

    assert parent.type == child.base

    tree = Module(body=[], type_ignores=[])

    if parent.type in built_in_types_names():
        import_from = arcor2.object_types.abstract.__name__
    else:
        import_from = f".{camel_case_to_snake_case(parent.type)}"

    tree.body.append(ImportFrom(module=import_from,
                                names=[alias(name=parent.type, asname=None)],
                                level=0))

    c = ClassDef(
        name=child.type,
        bases=[get_name(parent.type)],
        keywords=[],
        body=[
            Assign(
                targets=[Name(id='_ABSTRACT', ctx=Store())],
                value=NameConstant(value=False),
                type_comment=None)
        ],
        decorator_list=[])

    # TODO add docstring with description (if provided)
    c.body.append(Pass())

    tree.body.append(c)

    return tree


def object_instance_from_res(tree: Module, object_name: str, object_id: str, cls_name: str) -> None:

    main_body = find_function("main", tree).body
    last_assign_idx = -1

    for body_idx, body_item in enumerate(main_body):

        if isinstance(body_item, (Assign, AnnAssign)):
            last_assign_idx = body_idx

    assign = AnnAssign(
        target=Name(
            id=fix_object_name(object_name),
            ctx=Store()),
        annotation=Name(
            id=cls_name,
            ctx=Load()),
        value=Subscript(
            value=get_name_attr('res', "objects"),
            slice=Index(value=Str(
                s=object_id,
                kind='')),
            ctx=Load()),
        simple=1)

    main_body.insert(last_assign_idx + 1, assign)
