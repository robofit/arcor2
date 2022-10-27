import ast
import importlib
import inspect
import sys
from ast import (
    AST,
    Assert,
    Assign,
    Attribute,
    Call,
    ClassDef,
    Expr,
    FunctionDef,
    ImportFrom,
    Load,
    Module,
    Name,
    NodeTransformer,
    NodeVisitor,
    Raise,
    Store,
    Tuple,
    alias,
    fix_missing_locations,
)

import autopep8

from arcor2.source import SourceException


def parse(source: str) -> AST:

    try:
        return ast.parse(source, feature_version=sys.version_info[0:2])
    except (AssertionError, NotImplementedError, SyntaxError, ValueError) as e:
        raise SourceException("Failed to parse the code.") from e


def parse_def(type_def: type) -> AST:
    try:
        return parse(inspect.getsource(type_def))
    except OSError as e:
        raise SourceException("Failed to get the source code.") from e


def find_asserts(tree: FunctionDef) -> list[Assert]:
    class FindAsserts(NodeVisitor):
        def __init__(self) -> None:
            self.asserts: list[Assert] = []

        def visit_Assert(self, node: Assert) -> None:
            self.asserts.append(node)

    ff = FindAsserts()
    ff.visit(tree)

    return ff.asserts


def find_function(name: str, tree: Module | AST) -> FunctionDef:
    class FindFunction(NodeVisitor):
        def __init__(self) -> None:
            self.function_node: None | FunctionDef = None

        def visit_FunctionDef(self, node: FunctionDef) -> None:
            if node.name == name:
                self.function_node = node
                return

            if not self.function_node:
                self.generic_visit(node)

    ff = FindFunction()
    ff.visit(tree)

    if ff.function_node is None:
        raise SourceException(f"Function {name} not found.")

    return ff.function_node


def find_class_def(name: str, tree: Module | AST) -> ClassDef:
    class FindClassDef(NodeVisitor):
        def __init__(self) -> None:
            self.cls_def_node: None | ClassDef = None

        def visit_ClassDef(self, node: ClassDef) -> None:
            if node.name == name:
                self.cls_def_node = node
                return

            if not self.cls_def_node:
                self.generic_visit(node)

    ff = FindClassDef()
    ff.visit(tree)

    if ff.cls_def_node is None:
        raise SourceException(f"Class definition {name} not found.")

    return ff.cls_def_node


def add_import(node: Module, module: str, cls: str, try_to_import: bool = True) -> None:
    """Adds "from ... import ..." to the beginning of the script.

    Parameters
    ----------
    node
    module
    cls

    Returns
    -------
    """

    class AddImportTransformer(NodeTransformer):
        def __init__(self, module: str, cls: str) -> None:
            self.done = False
            self.module = module
            self.cls = cls

        def visit_ImportFrom(self, node: ImportFrom) -> ImportFrom:
            if node.module == self.module:

                for aliass in node.names:
                    if aliass.name == self.cls:
                        self.done = True
                        break
                else:
                    node.names.append(alias(name=self.cls, asname=None))
                    self.done = True

            return node

    if try_to_import:

        try:
            imported_mod = importlib.import_module(module)
        except ModuleNotFoundError as e:
            raise SourceException(e)

        try:
            getattr(imported_mod, cls)
        except AttributeError as e:
            raise SourceException(e)

    tr = AddImportTransformer(module, cls)
    node = tr.visit(node)

    if not tr.done:
        node.body.insert(0, ImportFrom(module=module, names=[alias(name=cls, asname=None)], level=0))


def add_method_call(
    body: list, instance: str, method: str, args: list, kwargs: list, returns: list[str], index: None | int = None
) -> None:
    """Adds method call to be body of a container. By default, it appends. When
    index is specified, it inserts.

    :param body:
    :param instance:
    :param method:
    :param args:
    :param kwargs:
    :param index:
    :param returns:
    :return:
    """

    call = Call(func=get_name_attr(instance, method), args=args, keywords=kwargs)

    cont: Expr | Assign | None = None

    if not returns:
        cont = Expr(value=call)
    elif len(returns) == 1:
        # TODO AnnAssign??
        cont = Assign(targets=[Name(id=returns[0], ctx=Store())], value=call)
    else:
        cont = Assign(targets=[Tuple(elts=[Name(id=ret, ctx=Store()) for ret in returns], ctx=Store())], value=call)

    if index is None:
        body.append(cont)
    else:
        body.insert(index, cont)


def get_name(name: str) -> Name:
    return Name(id=name, ctx=Load())


def get_name_attr(name: str, attr: str, ctx: type[Load] | type[Store] = Load) -> Attribute:
    return Attribute(value=get_name(name), attr=attr, ctx=ctx())


def tree_to_str(tree: AST) -> str:

    fix_missing_locations(tree)
    return autopep8.fix_code(ast.unparse(tree), options={"aggressive": 1, "max_line_length": 120})


def dump(tree: Module) -> str:
    return ast.dump(tree)


def find_raises(tree: FunctionDef) -> list[Raise]:
    class FindRaises(NodeVisitor):
        def __init__(self) -> None:
            self.raises: list[Raise] = []

        def visit_Raise(self, node: Raise) -> None:
            self.raises.append(node)

    ff = FindRaises()
    ff.visit(tree)

    return ff.raises
