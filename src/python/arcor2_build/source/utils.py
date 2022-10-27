import copy
from ast import (
    AnnAssign,
    Assign,
    Attribute,
    Call,
    ClassDef,
    Compare,
    Eq,
    ExceptHandler,
    Expr,
    FunctionDef,
    If,
    ImportFrom,
    Load,
    Module,
    Name,
    NameConstant,
    Pass,
    Return,
    Store,
    Str,
    Try,
    While,
    With,
    alias,
    arg,
    arguments,
    stmt,
    withitem,
)

import humps

import arcor2.data.common
from arcor2.cached import CachedProject
from arcor2.data.common import ActionPoint, Pose, Position, ProjectRobotJoints
from arcor2.exceptions import Arcor2Exception
from arcor2.source import SourceException
from arcor2.source.utils import add_import, find_function, tree_to_str

RES_MODULE = "arcor2_runtime.resources"
RES_CLS = "Resources"


def main_loop(tree: Module) -> While:
    main = find_function("main", tree)

    for node in main.body:
        if isinstance(node, While):  # TODO more specific condition (test for True argument)
            return node

    raise SourceException("Main loop not found.")


def empty_script_tree(project_id: str, add_main_loop: bool = True) -> Module:
    """Creates barebones of the script (empty 'main' function).

    Returns
    -------
    """

    main_body: list[stmt] = [
        Assign(
            targets=[Name(id="aps", ctx=Store())],
            value=Call(func=Name(id="ActionPoints", ctx=Load()), args=[Name(id="res", ctx=Load())], keywords=[]),
            type_comment=None,
        )
    ]

    if add_main_loop:
        main_body.append(While(test=NameConstant(value=True, kind=None), body=[Pass()], orelse=[]))
    else:
        """put there "pass" in order to make code valid even if there is no
        other statement (e.g. no object from resources)"""
        main_body.append(Pass())

    # TODO helper function for try ... except

    tree = Module(
        body=[
            FunctionDef(
                name="main",
                args=arguments(
                    posonlyargs=[],
                    args=[arg(arg="res", annotation=Name(id=RES_CLS, ctx=Load()), type_comment=None)],
                    vararg=None,
                    kwonlyargs=[],
                    kw_defaults=[],
                    kwarg=None,
                    defaults=[],
                ),
                body=main_body,
                decorator_list=[],
                returns=NameConstant(value=None, kind=None),
                type_comment=None,
            ),
            If(
                test=Compare(
                    left=Name(id="__name__", ctx=Load()), ops=[Eq()], comparators=[Str(s="__main__", kind="")]
                ),
                body=[
                    Try(
                        body=[
                            With(
                                items=[
                                    withitem(
                                        context_expr=Call(
                                            func=Name(id=RES_CLS, ctx=Load()),
                                            args=[],
                                            keywords=[],
                                        ),
                                        optional_vars=Name(id="res", ctx=Store()),
                                    )
                                ],
                                body=[
                                    Expr(
                                        value=Call(
                                            func=Name(id="main", ctx=Load()),
                                            args=[Name(id="res", ctx=Load())],
                                            keywords=[],
                                        )
                                    )
                                ],
                                type_comment=None,
                            )
                        ],
                        handlers=[
                            ExceptHandler(
                                type=Name(id=Exception.__name__, ctx=Load()),
                                name="e",
                                body=[
                                    Expr(
                                        value=Call(
                                            func=Name(id="print_exception", ctx=Load()),
                                            args=[Name(id="e", ctx=Load())],
                                            keywords=[],
                                        )
                                    )
                                ],
                            )
                        ],
                        orelse=[],
                        finalbody=[],
                    )
                ],
                orelse=[],
            ),
        ],
        type_ignores=[],
    )

    add_import(tree, "arcor2_runtime.exceptions", "print_exception", try_to_import=False)
    add_import(tree, RES_MODULE, RES_CLS, try_to_import=False)
    add_import(tree, "action_points", "ActionPoints", try_to_import=False)

    return tree


def global_action_points_class(project: CachedProject) -> str:
    tree = Module(body=[], type_ignores=[])

    tree.body.append(
        ImportFrom(
            module=arcor2.data.common.__name__,
            names=[
                alias(name=ActionPoint.__name__, asname=None),
                alias(name=Position.__name__, asname=None),
                alias(name=Pose.__name__, asname=None),
                alias(name=ProjectRobotJoints.__name__, asname=None),
            ],
            level=0,
        )
    )

    tree.body.append(
        ImportFrom(
            module=copy.__name__,
            names=[alias(name=copy.deepcopy.__name__, asname=None)],
            level=0,
        )
    )

    tree.body.append(
        ImportFrom(
            module=RES_MODULE,
            names=[alias(name=RES_CLS, asname=None)],
            level=0,
        )
    )

    aps_init_body: list[Assign | Pass] = []

    for ap in project.action_points:

        ap_cls_body: list[Assign] = [
            Assign(
                targets=[Attribute(value=Name(id="self", ctx=Load()), attr="_position", ctx=Store())],
                value=Attribute(
                    value=Call(
                        func=Attribute(
                            value=Attribute(value=Name(id="res", ctx=Load()), attr="project", ctx=Load()),
                            attr=CachedProject.bare_action_point.__name__,
                            ctx=Load(),
                        ),
                        args=[Str(s=ap.id, kind="")],
                        keywords=[],
                    ),
                    attr="position",
                    ctx=Load(),
                ),
                type_comment=None,
            )
        ]

        ap_type_name = humps.pascalize(ap.name)

        ap_joints_init_body: list[Assign] = []

        for joints in project.ap_joints(ap.id):
            ap_joints_init_body.append(
                Assign(
                    targets=[Attribute(value=Name(id="self", ctx=Load()), attr=f"_{joints.name}", ctx=Store())],
                    value=Call(
                        func=Attribute(
                            value=Attribute(value=Name(id="res", ctx=Load()), attr="project", ctx=Load()),
                            attr="joints",
                            ctx=Load(),
                        ),
                        args=[Str(s=joints.id, kind="")],
                        keywords=[],
                    ),
                    type_comment=None,
                )
            )

        if ap_joints_init_body:

            ap_joints_cls_def = ClassDef(
                name=f"{ap_type_name}Joints",
                bases=[],
                keywords=[],
                body=[
                    FunctionDef(
                        name="__init__",
                        args=arguments(
                            posonlyargs=[],
                            args=[
                                arg(arg="self", annotation=None, type_comment=None),
                                arg(arg="res", annotation=Name(id=RES_CLS, ctx=Load()), type_comment=None),
                            ],
                            vararg=None,
                            kwonlyargs=[],
                            kw_defaults=[],
                            kwarg=None,
                            defaults=[],
                        ),
                        body=ap_joints_init_body,
                        decorator_list=[],
                        returns=None,
                        type_comment=None,
                    )
                ],
                decorator_list=[],
            )

            for joints in project.ap_joints(ap.id):
                ap_joints_cls_def.body.append(
                    FunctionDef(
                        name=joints.name,
                        args=arguments(
                            posonlyargs=[],
                            args=[arg(arg="self", annotation=None, type_comment=None)],
                            vararg=None,
                            kwonlyargs=[],
                            kw_defaults=[],
                            kwarg=None,
                            defaults=[],
                        ),
                        body=[
                            Return(
                                value=Call(
                                    func=Name(id=copy.deepcopy.__name__, ctx=Load()),
                                    args=[
                                        Attribute(value=Name(id="self", ctx=Load()), attr=f"_{joints.name}", ctx=Load())
                                    ],
                                    keywords=[],
                                )
                            )
                        ],
                        decorator_list=[Name(id="property", ctx=Load())],
                        returns=Name(id=ProjectRobotJoints.__name__, ctx=Load()),
                        type_comment=None,
                    )
                )

            tree.body.append(ap_joints_cls_def)

            ap_cls_body.append(
                Assign(
                    targets=[Attribute(value=Name(id="self", ctx=Load()), attr="joints", ctx=Store())],
                    value=Call(
                        func=Name(id=f"{ap_type_name}Joints", ctx=Load()),
                        args=[Name(id="res", ctx=Load())],
                        keywords=[],
                    ),
                    type_comment=None,
                )
            )

        ap_orientations_init_body: list[Assign] = []

        for ori in project.ap_orientations(ap.id):
            ap_orientations_init_body.append(
                Assign(
                    targets=[Attribute(value=Name(id="self", ctx=Load()), attr=f"_{ori.name}", ctx=Store())],
                    value=Call(
                        func=Attribute(
                            value=Attribute(value=Name(id="res", ctx=Load()), attr="project", ctx=Load()),
                            attr="pose",
                            ctx=Load(),
                        ),
                        args=[Str(s=ori.id, kind="")],
                        keywords=[],
                    ),
                    type_comment=None,
                )
            )

        if ap_orientations_init_body:

            ap_orientations_cls_def = ClassDef(
                name=f"{ap_type_name}Poses",
                bases=[],
                keywords=[],
                body=[
                    FunctionDef(
                        name="__init__",
                        args=arguments(
                            posonlyargs=[],
                            args=[
                                arg(arg="self", annotation=None, type_comment=None),
                                arg(arg="res", annotation=Name(id=RES_CLS, ctx=Load()), type_comment=None),
                            ],
                            vararg=None,
                            kwonlyargs=[],
                            kw_defaults=[],
                            kwarg=None,
                            defaults=[],
                        ),
                        body=ap_orientations_init_body,
                        decorator_list=[],
                        returns=None,
                        type_comment=None,
                    )
                ],
                decorator_list=[],
            )

            for ori in project.ap_orientations(ap.id):
                ap_orientations_cls_def.body.append(
                    FunctionDef(
                        name=ori.name,
                        args=arguments(
                            posonlyargs=[],
                            args=[arg(arg="self", annotation=None, type_comment=None)],
                            vararg=None,
                            kwonlyargs=[],
                            kw_defaults=[],
                            kwarg=None,
                            defaults=[],
                        ),
                        body=[
                            Return(
                                value=Call(
                                    func=Name(id=copy.deepcopy.__name__, ctx=Load()),
                                    args=[
                                        Attribute(value=Name(id="self", ctx=Load()), attr=f"_{ori.name}", ctx=Load())
                                    ],
                                    keywords=[],
                                )
                            )
                        ],
                        decorator_list=[Name(id="property", ctx=Load())],
                        returns=Name(id=Pose.__name__, ctx=Load()),
                        type_comment=None,
                    )
                )

            tree.body.append(ap_orientations_cls_def)

            ap_cls_body.append(
                Assign(
                    targets=[Attribute(value=Name(id="self", ctx=Load()), attr="poses", ctx=Store())],
                    value=Call(
                        func=Name(id=f"{ap_type_name}Poses", ctx=Load()),
                        args=[Name(id="res", ctx=Load())],
                        keywords=[],
                    ),
                    type_comment=None,
                )
            )

        ap_cls_def = ClassDef(
            name=ap_type_name,
            bases=[],
            keywords=[],
            body=[
                FunctionDef(
                    name="__init__",
                    args=arguments(
                        posonlyargs=[],
                        args=[
                            arg(arg="self", annotation=None, type_comment=None),
                            arg(arg="res", annotation=Name(id=RES_CLS, ctx=Load()), type_comment=None),
                        ],
                        vararg=None,
                        kwonlyargs=[],
                        kw_defaults=[],
                        kwarg=None,
                        defaults=[],
                    ),
                    body=ap_cls_body,
                    decorator_list=[],
                    returns=None,
                    type_comment=None,
                )
            ],
            decorator_list=[],
        )

        # add copy property for position
        ap_cls_def.body.append(
            FunctionDef(
                name="position",
                args=arguments(
                    posonlyargs=[],
                    args=[arg(arg="self", annotation=None, type_comment=None)],
                    vararg=None,
                    kwonlyargs=[],
                    kw_defaults=[],
                    kwarg=None,
                    defaults=[],
                ),
                body=[
                    Return(
                        value=Call(
                            func=Name(id=copy.deepcopy.__name__, ctx=Load()),
                            args=[Attribute(value=Name(id="self", ctx=Load()), attr="_position", ctx=Load())],
                            keywords=[],
                        )
                    )
                ],
                decorator_list=[Name(id="property", ctx=Load())],
                returns=Name(id=Position.__name__, ctx=Load()),
                type_comment=None,
            )
        )

        tree.body.append(ap_cls_def)

        aps_init_body.append(
            Assign(
                targets=[Attribute(value=Name(id="self", ctx=Load()), attr=ap.name, ctx=Store())],
                value=Call(func=Name(id=ap_type_name, ctx=Load()), args=[Name(id="res", ctx=Load())], keywords=[]),
                type_comment=None,
            )
        )

    if not aps_init_body:  # there are no action points
        aps_init_body.append(Pass())

    aps_cls_def = ClassDef(
        name="ActionPoints",
        bases=[],
        keywords=[],
        body=[
            FunctionDef(
                name="__init__",
                args=arguments(
                    posonlyargs=[],
                    args=[
                        arg(arg="self", annotation=None, type_comment=None),
                        arg(arg="res", annotation=Name(id=RES_CLS, ctx=Load()), type_comment=None),
                    ],
                    vararg=None,
                    kwonlyargs=[],
                    kw_defaults=[],
                    kwarg=None,
                    defaults=[],
                ),
                body=aps_init_body,
                decorator_list=[],
                returns=None,
                type_comment=None,
            )
        ],
        decorator_list=[],
    )

    tree.body.append(aps_cls_def)
    return tree_to_str(tree)


def find_last_assign(tree: FunctionDef) -> int:
    """This is intended to find last assign to a variable in the generated
    script (without logic).

    :param tree:
    :return:
    """

    for body_idx, body_item in reversed(list(enumerate(tree.body))):
        if isinstance(body_item, (Assign, AnnAssign)):
            return body_idx

    raise Arcor2Exception("Assign not found.")
