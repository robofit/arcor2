#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from horast import parse, unparse
import typed_ast.ast3
from typed_ast.ast3 import If, FunctionDef, Module, While, NameConstant, Pass, Compare, Name, Load, Eq, Expr, Call, NodeVisitor, NodeTransformer, ImportFrom, Assign, arguments, Str, keyword, fix_missing_locations, Attribute, Store, alias
import autopep8  # type: ignore
import os
import stat
from typing import Dict, Optional, List, Any, Set
import importlib
import typed_astunparse
import static_typing as st


validator = st.ast_manipulation.AstValidator[typed_ast.ast3](mode="strict")


class GenerateSourceException(Exception):
    pass


def empty_script_tree() -> Module:
    """
    Creates barebones of the script (empty 'main' function).

    Returns
    -------

    """

    return Module(body=[
        FunctionDef(name="main",
                        body=[While(test=NameConstant(value=True), body=[Pass()], orelse=[])],
                        decorator_list=[],
                        args=arguments(args=[],
                                           vararg=None,
                                           kwonlyargs=[],
                                           kw_defaults=[],
                                           kwarg=None,
                                           defaults=[]),
                        returns=NameConstant(value=None)),

        If(test=Compare(left=Name(id='__name__', ctx=Load()),
                                ops=[Eq()],
                                comparators=[Str(s='__main__')],
                                ),
               body=[Expr(value=Call(func=Name(id='main', ctx=Load()),
                                             args=[],
                                             keywords=[]))],
               orelse=[]
               )
    ])


def find_function(name, tree) -> FunctionDef:

    class FindFunction(NodeVisitor):

        def __init__(self):
            self.function_node = None

        def visit_FunctionDef(self, node: FunctionDef) -> None:
            if node.name == name:
                self.function_node = node
                return

            if not self.function_node:
                self.generic_visit(node)

    ff = FindFunction()
    ff.visit(tree)

    return ff.function_node


def add_import(node: Module, module: str, cls: str) -> None:
    """
    Adds "from ... import ..." to the beginning of the script.

    Parameters
    ----------
    node
    module
    cls

    Returns
    -------

    """

    class AddImportTransformer(NodeTransformer):

        def __init__(self, module, cls):
            self.done = False

        def visit_ImportFrom(self, node: ImportFrom) -> ImportFrom:
            if node.module == module:

                for aliass in node.names:
                    if aliass.name == cls:
                        self.done = True
                        break
                else:
                    node.names.append(alias(name=cls, asname=None))
                    self.done = True

            return node

    try:
        imported_mod = importlib.import_module(module)
    except ModuleNotFoundError as e:
        raise GenerateSourceException(e)

    try:
        getattr(imported_mod, cls)
    except AttributeError as e:
        raise GenerateSourceException(e)

    tr = AddImportTransformer(module, cls)
    node = tr.visit(node)

    if not tr.done:
        node.body.insert(0, ImportFrom(module=module, names=[alias(name=cls, asname=None)], level=0))


def add_cls_inst(node: Module, cls: str, name: str, kwargs: Optional[Dict] = None, kwargs2parse: Optional[Dict] = None) -> None:

    class FindImport(NodeVisitor):

        def __init__(self, cls: str):

            self.found = False

        def visit_ImportFrom(self, node: ImportFrom):

            for alias in node.names:
                if alias.name == cls:
                    self.found = True

            if not self.found:
                self.generic_visit(node)

    class FindClsInst(NodeVisitor):

        def __init__(self):

            self.found = False

        def visit_FunctionDef(self, node: FunctionDef) -> None:

            if node.name == 'main':

                for item in node.body:

                    if isinstance(item, Assign) and item.targets[0].id == name:

                        if item.value.func.id != cls:
                            raise GenerateSourceException("Name '{}' already used for instance of '{}'!".format(name, item.value.func.id))

                        self.found = True
                        # TODO update arguments?

            if not self.found:
                self.generic_visit(node)

    class AddClsInst(NodeTransformer):

        def visit_FunctionDef(self, node: FunctionDef) -> FunctionDef:

            if node.name == 'main':

                kw = []

                if kwargs:
                    for k, v in kwargs.items():
                        kw.append(keyword(arg=k, value=v))

                if kwargs2parse:
                    for k, v in kwargs2parse.items():
                        kw.append(keyword(arg=k, value=parse(v)))

                node.body.insert(0, Assign(targets=[Name(id=name, ctx=Store())],
                                               value=Call(func=Name(id=cls, ctx=Load()),
                                                              args=[],
                                                              keywords=kw)))

            return node

    find_import = FindImport(cls)
    find_import.visit(node)

    if not find_import.found:
        raise GenerateSourceException("Class '{}' not imported!".format(cls))

    vis = FindClsInst()
    vis.visit(node)

    if not vis.found:

        tr = AddClsInst()
        node = tr.visit(node)


def add_method_call(tree: Module, instance: str, method: str, init: bool, args: List, kwargs: Optional[Dict] = None):
    """
    Places method call after block where instances are created.

    Parameters
    ----------
    tree
    instance
    init
    args
    kwargs

    Returns
    -------

    """

    main_body = find_function("main", tree).body
    last_assign_idx = None

    for body_idx, body_item in enumerate(main_body):

        # TODO check if instance exists!

        if isinstance(body_item, Assign):
            last_assign_idx = body_idx

    if not last_assign_idx:
        raise GenerateSourceException()

    # TODO iterate over args/kwargs
    # TODO check actual number of method's arguments (and types?)
    main_body.insert(last_assign_idx+1, Expr(value=Call(func=Attribute(value=Name(id=instance,
                                                                                                ctx=Load()),
                                                                                 attr=method,
                                                                                 ctx=Load()),
                                                              args=args, keywords=[])))


def get_name(name):

    return Name(id=name, ctx=Load())


def tree_to_script(tree: Module, out_file: str) -> None:

    # TODO why this fails?
    # validator.visit(tree)

    fix_missing_locations(tree)
    generated_code = unparse(tree)
    generated_code = autopep8.fix_code(generated_code, options={'aggressive': 1})

    with open(out_file, "w") as f:

        f.write("#!/usr/bin/env python3\n")
        f.write("# -*- coding: utf-8 -*-\n\n")
        f.write(generated_code)

    st = os.stat(out_file)
    os.chmod(out_file, st.st_mode | stat.S_IEXEC)


def dump(tree: Module) -> None:

    return typed_astunparse.dump(tree)


def main() -> None:

    tree = empty_script_tree()

    # TODO turn following into proper test
    add_import(tree, "arcor2.core", "Workspace")
    add_import(tree, "arcor2.core", "Robot")
    add_import(tree, "arcor2.core", "Robot")
    add_import(tree, "arcor2.core", "WorldObject")

    try:
        add_import(tree, "arcor2.core", "NonExistingClass")
    except GenerateSourceException as e:
        print(e)

    try:
        add_import(tree, "NonExistingModule", "NonExistingClass")
    except GenerateSourceException as e:
        print(e)

    add_cls_inst(tree, "Robot", "robot", kwargs2parse={"end_effectors": '("gripper",)'})
    add_cls_inst(tree, "Robot", "robot")
    add_cls_inst(tree, "Workspace", "workspace")

    try:
        add_cls_inst(tree, "WorldObject", "robot")
    except GenerateSourceException as e:
        print(e)

    add_cls_inst(tree, "WorldObject", "wo")

    try:
        add_cls_inst(tree, "NonExistingType", "test")
    except GenerateSourceException as e:
        print(e)

    add_method_call(tree, "workspace", "add_child", True, [get_name("robot")])
    add_method_call(tree, "workspace", "add_child", True, [get_name("wo")])

    tree_to_script(tree, "output.py")


if __name__ == "__main__":
    main()
