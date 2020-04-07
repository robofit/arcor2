from typing import Union
from typing_extensions import Literal

from typed_ast.ast3 import Assign, Name, ClassDef, Str, Module, \
    ImportFrom, alias, Pass, AnnAssign, Store, Load, Subscript, Index

from arcor2.data.object_type import ObjectTypeMeta
from arcor2.helpers import camel_case_to_snake_case
from arcor2.source import SourceException
from arcor2.source.utils import get_name, tree_to_str, find_function, get_name_attr
from arcor2.object_types_utils import built_in_types_names, meta_from_def, object_actions
import arcor2.helpers as hlp
import arcor2.object_types
from arcor2.object_types import Generic
from arcor2.parameter_plugins import TYPE_TO_PLUGIN


def check_object_type(object_type_source: str, type_name: str) -> None:
    """
    Checks whether the object type source is a valid one.
    :param object_type_source:
    :return:
    """
    try:
        type_def = hlp.type_def_from_source(object_type_source, type_name, Generic)
    except hlp.TypeDefException as e:
        raise SourceException(e)

    meta_from_def(type_def, False)
    object_actions(TYPE_TO_PLUGIN, type_def, object_type_source)


def fix_object_name(object_id: str) -> str:

    return camel_case_to_snake_case(object_id).replace(' ', '_')


# TODO could this be done like this https://stackoverflow.com/a/9269964/3142796 ??
def new_object_type_source(parent: ObjectTypeMeta, child: ObjectTypeMeta) -> str:

    assert parent.type == child.base

    tree = Module(body=[], type_ignores=[])

    if parent.type in built_in_types_names():
        import_from = arcor2.object_types.__name__
    else:
        import_from = camel_case_to_snake_case(parent.type)

    tree.body.append(ImportFrom(module=import_from,
                                names=[alias(name=parent.type, asname=None)],
                                level=0))

    c = ClassDef(name=child.type,
                 bases=[get_name(parent.type)],
                 keywords=[],
                 body=[],
                 decorator_list=[])

    # TODO add docstring with description (if provided)
    c.body.append(Pass())

    tree.body.append(c)

    return tree_to_str(tree)


def object_instance_from_res(tree: Module, object_name: str, object_id: str, cls_name: str,
                             cls_type: Union[Literal["objects"], Literal["services"]]) -> None:

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
            value=get_name_attr('res', cls_type),
            slice=Index(value=Str(
                s=object_id,
                kind='')),
            ctx=Load()),
        simple=1)

    main_body.insert(last_assign_idx + 1, assign)
