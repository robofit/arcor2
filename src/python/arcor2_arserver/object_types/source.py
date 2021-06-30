from ast import AST, Assign, Call, ClassDef, ImportFrom, Module, Name, NameConstant, Pass, Store, alias

import humps

import arcor2.object_types
from arcor2.exceptions import Arcor2NotImplemented
from arcor2.object_types.utils import built_in_types_names
from arcor2.source import SourceException
from arcor2.source.utils import find_function, find_raises, get_name
from arcor2_arserver_data.objects import ObjectTypeMeta


# TODO could this be done like this https://stackoverflow.com/a/9269964/3142796 ??
def new_object_type(parent: ObjectTypeMeta, child: ObjectTypeMeta) -> AST:

    assert parent.type == child.base

    tree = Module(body=[], type_ignores=[])

    if parent.type in built_in_types_names():
        import_from = arcor2.object_types.abstract.__name__
    else:
        import_from = f".{humps.depascalize(parent.type)}"

    tree.body.append(ImportFrom(module=import_from, names=[alias(name=parent.type, asname=None)], level=0))

    c = ClassDef(
        name=child.type,
        bases=[get_name(parent.type)],
        keywords=[],
        body=[
            Assign(
                targets=[Name(id="_ABSTRACT", ctx=Store())],
                value=NameConstant(value=False, kind=None),
                type_comment=None,
            )
        ],
        decorator_list=[],
    )

    # TODO add docstring with description (if provided)
    c.body.append(Pass())

    tree.body.append(c)

    return tree


def function_implemented(tree: AST, func_name: str) -> bool:
    """Body of unimplemented function (e.g. object/service feature) contains
    only 'raise Arcor2NotImplemented()'.

    :param tree:
    :return:
    """

    try:
        func_def = find_function(func_name, tree)
    except SourceException:
        return False

    raises = find_raises(func_def)

    if len(raises) != 1:
        return True

    exc = raises[0].exc

    if isinstance(exc, Call):
        # raise Arcor2NotImplemented("something")

        assert isinstance(exc.func, Name)

        if exc.func.id == Arcor2NotImplemented.__name__:
            return False

    if isinstance(exc, Name) and exc.id == Arcor2NotImplemented.__name__:
        # raise Arcor2NotImplemented
        return False

    return True
