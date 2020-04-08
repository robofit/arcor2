import importlib
import os
import stat
from typing import List, Optional, Dict, Any, Union, Type
import re

import autopep8  # type: ignore
import typed_astunparse
from horast import parse, unparse

from typed_ast.ast3 import Module, Assign, Name, Store, Load, Attribute, FunctionDef, \
    NameConstant, Pass, arguments, If, Compare, Eq, Expr, Call, alias, keyword, ClassDef, arg, Return, While, Str, \
    ImportFrom, NodeVisitor, NodeTransformer, fix_missing_locations, Try, ExceptHandler, With, withitem, Subscript, \
    Index, Assert, AST, stmt

from arcor2.data.common import Project, ActionPoint
from arcor2.source import SourceException, SCRIPT_HEADER
import arcor2.data.common


def main_loop_body(tree: Module) -> List[Any]:
    main = find_function("main", tree)

    for node in main.body:
        if isinstance(node, While):  # TODO more specific condition (test for True argument)
            return node.body

    raise SourceException("Main loop not found.")


def empty_script_tree(add_main_loop: bool = True) -> Module:
    """
    Creates barebones of the script (empty 'main' function).

    Returns
    -------

    """

    main_body: List[stmt] = []

    if add_main_loop:
        main_body.append(While(
                        test=NameConstant(value=True),
                        body=[Pass()],
                        orelse=[]))
    else:
        """
        put there "pass" in order to make code valid even if there is no other statement (e.g. no object from resources)
        """
        main_body.append(Pass())

    # TODO helper function for try ... except

    tree = Module(
        body=[
            FunctionDef(
                name='main',
                args=arguments(
                    args=[arg(
                        arg='res',
                        annotation=Name(
                            id='Resources',
                            ctx=Load()),
                        type_comment=None)],
                    vararg=None,
                    kwonlyargs=[],
                    kw_defaults=[],
                    kwarg=None,
                    defaults=[]),
                body=main_body,
                decorator_list=[],
                returns=NameConstant(value=None),
                type_comment=None),
            If(
                test=Compare(
                    left=Name(
                        id='__name__',
                        ctx=Load()),
                    ops=[Eq()],
                    comparators=[Str(
                        s='__main__',
                        kind='')]),
                body=[Try(
                    body=[With(
                        items=[withitem(
                            context_expr=Call(
                                func=Name(
                                    id='Resources',
                                    ctx=Load()),
                                args=[],
                                keywords=[]),
                            optional_vars=Name(
                                id='res',
                                ctx=Store()))],
                        body=[Expr(value=Call(
                            func=Name(
                                id='main',
                                ctx=Load()),
                            args=[Name(
                                id='res',
                                ctx=Load())],
                            keywords=[]))],
                        type_comment=None)],
                    handlers=[ExceptHandler(
                        type=Name(
                            id='Exception',
                            ctx=Load()),
                        name='e',
                        body=[Expr(value=Call(
                            func=Name(
                                id='print_exception',
                                ctx=Load()),
                            args=[Name(
                                id='e',
                                ctx=Load())],
                            keywords=[]))])],
                    orelse=[],
                    finalbody=[])],
                orelse=[])],
        type_ignores=[])

    add_import(tree, "arcor2.helpers", "print_exception")
    add_import(tree, "resources", "Resources", try_to_import=False)

    return tree


def find_asserts(tree: FunctionDef) -> List[Assert]:
    class FindAsserts(NodeVisitor):

        def __init__(self) -> None:
            self.asserts: List[Assert] = []

        def visit_Assert(self, node: Assert) -> None:
            self.asserts.append(node)

    ff = FindAsserts()
    ff.visit(tree)

    return ff.asserts


def find_function(name: str, tree: Union[Module, AST]) -> FunctionDef:
    class FindFunction(NodeVisitor):

        def __init__(self) -> None:
            self.function_node: Optional[FunctionDef] = None

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


def add_import(node: Module, module: str, cls: str, try_to_import: bool = True) -> None:
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


def add_cls_inst(node: Module, cls: str, name: str, kwargs: Optional[Dict] = None,
                 kwargs2parse: Optional[Dict] = None) -> None:
    class FindImport(NodeVisitor):

        def __init__(self, cls: str) -> None:

            self.found = False
            self.cls = cls

        def visit_ImportFrom(self, node: ImportFrom) -> None:

            for node_alias in node.names:
                if node_alias.name == self.cls:
                    self.found = True

            if not self.found:
                self.generic_visit(node)

    class FindClsInst(NodeVisitor):

        def __init__(self) -> None:

            self.found = False

        def visit_FunctionDef(self, node: FunctionDef) -> None:

            if node.name == 'main':

                for item in node.body:

                    if isinstance(item, Assign):

                        assert isinstance(item.targets[0], Name)

                        if item.targets[0].id == name:

                            # TODO assert for item.value
                            if item.value.func.id != cls:  # type: ignore
                                raise SourceException(
                                    "Name '{}' already used for instance of '{}'!".
                                    format(name, item.value.func.id))  # type: ignore

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
        raise SourceException("Class '{}' not imported!".format(cls))

    vis = FindClsInst()
    vis.visit(node)

    if not vis.found:
        tr = AddClsInst()
        node = tr.visit(node)


def append_method_call(body: List, instance: str, method: str, args: List, kwargs: List) -> None:
    body.append(Expr(value=Call(func=get_name_attr(instance, method),
                                args=args,
                                keywords=kwargs)))


def add_method_call_in_main(tree: Module, instance: str, method: str, args: List, kwargs: List) -> None:
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
        raise SourceException()

    # TODO iterate over args/kwargs
    # TODO check actual number of method's arguments (and types?)
    main_body.insert(last_assign_idx + 1, Expr(value=Call(func=get_name_attr(instance, method),
                                                          args=args, keywords=[])))


def get_name(name: str) -> Name:
    return Name(id=name, ctx=Load())


def get_name_attr(name: str, attr: str, ctx: Union[Type[Load], Type[Store]] = Load) -> Attribute:
    return Attribute(
        value=get_name(name),
        attr=attr,
        ctx=ctx())


def tree_to_str(tree: Module) -> str:
    # TODO why this fails?
    # validator.visit(tree)

    fix_missing_locations(tree)
    generated_code: str = unparse(tree)
    generated_code = autopep8.fix_code(generated_code, options={'aggressive': 1})

    return generated_code


def make_executable(path_to_file: str) -> None:
    st = os.stat(path_to_file)
    os.chmod(path_to_file, st.st_mode | stat.S_IEXEC)


def tree_to_script(tree: Module, out_file: str, executable: bool) -> None:
    generated_code = tree_to_str(tree)

    with open(out_file, "w") as f:
        f.write(SCRIPT_HEADER)
        f.write(generated_code)

    if executable:
        make_executable(out_file)


def clean(x):
    return re.sub('\W|^(?=\d)', '_', x)  # noqa


def global_action_points_class(project: Project) -> str:
    tree = Module(body=[])
    tree.body.append(ImportFrom(
        module=arcor2.data.common.__name__,
        names=[alias(
            name=ActionPoint.__name__,
            asname=None)],
        level=0))
    tree.body.append(ImportFrom(
        module='resources',
        names=[alias(
            name='Resources',
            asname=None)],
        level=0))

    cls_def = ClassDef(
        name='ActionPoints',
        bases=[],
        keywords=[],
        body=[
            FunctionDef(
                name='__init__',
                args=arguments(
                    args=[
                        arg(
                            arg='self',
                            annotation=None,
                            type_comment=None),
                        arg(
                            arg='res',
                            annotation=Name(
                                id='Resources',
                                ctx=Load()),
                            type_comment=None)],
                    vararg=None,
                    kwonlyargs=[],
                    kw_defaults=[],
                    kwarg=None,
                    defaults=[]),
                body=[Assign(
                    targets=[Attribute(
                        value=Name(
                            id='self',
                            ctx=Load()),
                        attr='_res',
                        ctx=Store())],
                    value=Name(
                        id='res',
                        ctx=Load()),
                    type_comment=None)],
                decorator_list=[],
                returns=None,
                type_comment=None)],
        decorator_list=[])

    for ap in project.action_points:
        fd = FunctionDef(
            name=clean(ap.name),  # TODO avoid possible collisions
            args=arguments(
                args=[arg(arg='self', annotation=None, type_comment=None)],
                vararg=None,
                kwonlyargs=[],
                kw_defaults=[],
                kwarg=None,
                defaults=[]),
            body=[Return(value=Call(
                func=Attribute(
                    value=Attribute(
                        value=Attribute(
                            value=Name(
                                id='self',
                                ctx=Load()),
                            attr='_res',
                            ctx=Load()),
                        attr='project',
                        ctx=Load()),
                    attr='action_point',
                    ctx=Load()),
                args=[Str(
                    s=ap.id,
                    kind='')],
                keywords=[]))],
            decorator_list=[Name(
                id='property',
                ctx=Load())],
            returns=Name(
                id='ActionPoint',
                ctx=Load()),
            type_comment=None)

        cls_def.body.append(fd)

    tree.body.append(cls_def)
    return tree_to_str(tree)


def global_actions_class(project: Project) -> str:
    tree = Module(body=[])
    tree.body.append(ImportFrom(
        module='resources',
        names=[alias(
            name='Resources',
            asname=None)],
        level=0))

    cls_def = ClassDef(
        name='Actions',
        bases=[],
        keywords=[],
        body=[
            FunctionDef(
                name='__init__',
                args=arguments(
                    args=[
                        arg(
                            arg='self',
                            annotation=None,
                            type_comment=None),
                        arg(
                            arg='res',
                            annotation=Name(
                                id='Resources',
                                ctx=Load()),
                            type_comment=None)],
                    vararg=None,
                    kwonlyargs=[],
                    kw_defaults=[],
                    kwarg=None,
                    defaults=[]),
                body=[Assign(
                    targets=[Attribute(
                        value=Name(
                            id='self',
                            ctx=Load()),
                        attr='_res',
                        ctx=Store())],
                    value=Name(
                        id='res',
                        ctx=Load()),
                    type_comment=None)],
                decorator_list=[],
                returns=None,
                type_comment=None)],
        decorator_list=[])

    for ap in project.action_points:
        for action in ap.actions:
            ac_obj, ac_type = action.parse_type()

            m = FunctionDef(
                name=clean(action.name),
                args=arguments(
                    args=[arg(
                        arg='self',
                        annotation=None,
                        type_comment=None)],
                    vararg=None,
                    kwonlyargs=[],
                    kw_defaults=[],
                    kwarg=None,
                    defaults=[]),
                body=[Expr(value=Call(
                    func=Attribute(
                        value=Subscript(
                            value=Attribute(
                                value=Attribute(
                                    value=Name(
                                        id='self',
                                        ctx=Load()),
                                    attr='_res',
                                    ctx=Load()),
                                attr='all_instances',
                                ctx=Load()),
                            slice=Index(value=Str(
                                s=ac_obj,
                                kind='')),
                            ctx=Load()),
                        attr=ac_type,
                        ctx=Load()),
                    args=[Attribute(
                        value=Attribute(
                            value=Name(
                                id='self',
                                ctx=Load()),
                            attr='_res',
                            ctx=Load()),
                        attr=clean(action.name),
                        ctx=Load())],
                    keywords=[]))],
                decorator_list=[],
                returns=None,
                type_comment=None)

            cls_def.body.append(m)

    tree.body.append(cls_def)
    return tree_to_str(tree)


def derived_resources_class(project: Project) -> str:
    # TODO temporary and ugly solution of circular import
    import arcor2.resources
    from arcor2.resources import ResourcesBase

    tree = Module(body=[])

    parameters = [(act.id, clean(act.name)) for aps in project.action_points for act in aps.actions]

    add_import(tree, arcor2.resources.__name__, ResourcesBase.__name__)

    derived_cls_name = "Resources"

    init_body: List = [Expr(value=Call(
        func=Attribute(value=Call(func=Name(id='super', ctx=Load()),
                                  args=[Name(id=derived_cls_name, ctx=Load()),
                                        Name(id='self', ctx=Load())], keywords=[]),
                       attr='__init__', ctx=Load()), args=[Str(s=project.id)],
        keywords=[]))]

    for a_id, a_name in parameters:
        init_body.append(Assign(targets=[get_name_attr("self", "_" + a_name, Store)],
                                value=Call(
                                    func=get_name_attr("self", "parameters"),
                                    args=[Str(s=a_id)], keywords=[])))

    cls_def = ClassDef(name=derived_cls_name,
                       bases=[Name(id=ResourcesBase.__name__, ctx=Load())],
                       keywords=[],
                       body=[FunctionDef(name='__init__', args=arguments(args=[arg(arg='self', annotation=None)],
                                                                         vararg=None, kwonlyargs=[],
                                                                         kw_defaults=[], kwarg=None,
                                                                         defaults=[]), body=init_body,
                                         decorator_list=[], returns=None)], decorator_list=[])

    tree.body.append(cls_def)

    for a_id, a_name in parameters:
        cls_def.body.append(FunctionDef(
            name=a_name,
            args=arguments(
                args=[arg(
                    arg='self',
                    annotation=None,
                    type_comment=None)],
                vararg=None,
                kwonlyargs=[],
                kw_defaults=[],
                kwarg=None,
                defaults=[]),
            body=[
                Expr(value=Call(
                    func=Attribute(value=Name(id='self', ctx=Load()), attr='print_info', ctx=Load()),
                    args=[
                        Str(
                            s=a_id,
                            kind=''),
                        get_name_attr('self', '_' + a_name)],
                    keywords=[])),
                Return(value=get_name_attr('self', '_' + a_name))],
            decorator_list=[Name(
                id='property',
                ctx=Load())],
            returns=None,
            type_comment=None))

    return tree_to_str(tree)


def dump(tree: Module) -> str:
    return typed_astunparse.dump(tree)
