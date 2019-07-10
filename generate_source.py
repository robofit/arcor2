#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from horast import parse, unparse  # type: ignore
import typed_ast.ast3
from typed_ast.ast3 import If, FunctionDef, Module, While, NameConstant, Pass, Compare, Name, Load, Eq, Expr, Call, \
    NodeVisitor, NodeTransformer, ImportFrom, Assign, arguments, Str, keyword, fix_missing_locations, Attribute, \
    alias, ClassDef, arg, AnnAssign, Subscript, Index, Return, Store
import autopep8  # type: ignore
import os
import stat
from typing import Dict, Optional, List, Set
import importlib
import typed_astunparse  # type: ignore
import static_typing as st  # type: ignore
from arcor2.resources import ResourcesBase
from arcor2.helpers import convert_cc

SCRIPT_HEADER = "#!/usr/bin/env python3\n""# -*- coding: utf-8 -*-\n\n"

validator = st.ast_manipulation.AstValidator[typed_ast.ast3](mode="strict")


class GenerateSourceException(Exception):
    pass


def get_object_actions(object_source: str) -> List:

    tree = object_cls_def(object_source)

    action_attr: Dict = {}
    ret: List = []

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
        action_attr[node.targets[0].value.id] = {}
        for kwarg in node.value.keywords:
            action_attr[node.targets[0].value.id][kwarg.arg] = kwarg.value.value

    # TODO add missing attributes (e.g. free, composite, blackbox) to action_attr?

    for node in tree.body:

        if not isinstance(node, FunctionDef):
            continue

        for decorator in node.decorator_list:
            if decorator.id == "action":
                if node.name in action_attr:
                    break
                raise GenerateSourceException(f"Method {node.name} has @action decorator, but no metadata.")
        else:
            raise GenerateSourceException(f"Method {node.name} without @action decorator.")

        d: Dict = {"name": node.name, "action_args": []}
        d.update(action_attr[node.name])

        for arg in node.args.args:

            if arg.arg == "self":
                continue

            d["action_args"].append({"name": arg.arg, "type": arg.annotation.id})

        ret.append(d)

    return ret


def object_type_info(object_source: str) -> Dict:

    tree = object_cls_def(object_source)

    d = {"base": "", "description": ""}

    if len(tree.bases) > 1:
        raise GenerateSourceException("Only one base class is supported!")

    if tree.bases:
        d["base"] = tree.bases[0].id

    for node in tree.body:
        if not isinstance(node, Assign):
            continue
        if len(node.targets) == 1 and isinstance(node.targets[0], Name) and node.targets[0].id == "__DESCRIPTION__":
            d["description"] = node.value.s

    return d


def object_cls_def(object_source: str) -> ClassDef:

    tree = parse(object_source)

    cls_def = None

    for node in tree.body:

        if isinstance(node, ClassDef):
            if cls_def is None:
                cls_def = node
                break
            else:
                raise GenerateSourceException("Multiple class definition!")
    else:
        raise GenerateSourceException("No class definition!")

    return cls_def


def fix_object_name(object_id: str) -> str:

    return convert_cc(object_id).replace(' ', '_')


def program_src(project: Dict, scene: Dict, built_in_objects: Set) -> str:

    tree = empty_script_tree()
    add_import(tree, "resources", "Resources", try_to_import=False)
    add_cls_inst(tree, "Resources", "res")

    # TODO api???
    # get object instances from resources object
    for obj in scene["objects"]:

        if obj["type"] in built_in_objects:
            add_import(tree, "arcor2.object_types", obj["type"], try_to_import=False)
        else:
            add_import(tree, "object_types." + convert_cc(obj["type"]), obj["type"], try_to_import=False)

        object_instance_from_res(tree, obj["id"], obj["type"])

    add_logic_to_loop(tree, project)

    return tree_to_str(tree)


def add_logic_to_loop(tree, project: Dict):

    loop = main_loop_body(tree)

    actions_cache = {}
    first_action_id = None
    last_action_id = None

    for obj in project["objects"]:
        for aps in obj["action_points"]:
            for act in aps["actions"]:
                actions_cache[act["id"]] = act
                if act["inputs"][0]["default"] == "start":
                    first_action_id = act["id"]
                elif act["outputs"][0]["default"] == "end":
                    last_action_id = act["id"]

    if first_action_id is None:
        raise GenerateSourceException("'start' action not found.")

    if last_action_id is None:
        raise GenerateSourceException("'end' action not found.")

    next_action_id = first_action_id

    while True:

        act = actions_cache[next_action_id]

        if len(loop) == 1 and isinstance(loop[0], Pass):
            # pass is not necessary now
            loop.clear()

        ac_obj, ac_type = act["type"].split('/')
        append_method_call(loop, fix_object_name(ac_obj), ac_type, [], [keyword(
                                                                      arg=None,
                                                                      value=Attribute(
                                                                        value=Name(
                                                                          id='res',
                                                                          ctx=Load()),
                                                                        attr=act["id"],
                                                                        ctx=Load()))])

        if act["id"] == last_action_id:
            break

        next_action_id = act["outputs"][0]["default"]


def object_instance_from_res(tree: Module, object_id: str, cls_name: str) -> None:

    main_body = find_function("main", tree).body
    last_assign_idx = None

    for body_idx, body_item in enumerate(main_body):

        if isinstance(body_item, (Assign, AnnAssign)):
            last_assign_idx = body_idx

    if last_assign_idx is None:
        raise GenerateSourceException()

    assign = AnnAssign(
        target=Name(
            id=fix_object_name(object_id),
            ctx=Store()),
        annotation=Name(
            id=cls_name,
            ctx=Load()),
        value=Subscript(
            value=Attribute(
                value=Name(
                    id='res',
                    ctx=Load()),
                attr='objects',
                ctx=Load()),
            slice=Index(value=Str(
                s=object_id,
                kind='')),
            ctx=Load()),
        simple=1)

    main_body.insert(last_assign_idx + 1, assign)


def main_loop_body(tree) -> List:

    main_body = find_function("main", tree).body

    for node in main_body:
        if isinstance(node, While):  # TODO more specific condition
            return node.body

    raise GenerateSourceException("Main loop not found.")


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

    if try_to_import:

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


def add_cls_inst(node: Module, cls: str, name: str, kwargs: Optional[Dict] = None,
                 kwargs2parse: Optional[Dict] = None) -> None:
    class FindImport(NodeVisitor):

        def __init__(self, cls: str):

            self.found = False

        def visit_ImportFrom(self, node: ImportFrom):

            for node_alias in node.names:
                if node_alias.name == cls:
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
                            raise GenerateSourceException(
                                "Name '{}' already used for instance of '{}'!".format(name, item.value.func.id))

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


def append_method_call(body: List, instance: str, method: str, args: List, kwargs: List):

    body.append(Expr(value=Call(func=Attribute(value=Name(id=instance, ctx=Load()), attr=method, ctx=Load()),
                                args=args,
                                keywords=kwargs)))


def add_method_call_in_main(tree: Module, instance: str, method: str, args: List, kwargs: List):
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
    main_body.insert(last_assign_idx + 1, Expr(value=Call(func=Attribute(value=Name(id=instance,
                                                                                    ctx=Load()),
                                                                         attr=method,
                                                                         ctx=Load()),
                                                          args=args, keywords=[])))


def get_name(name):
    return Name(id=name, ctx=Load())


def tree_to_str(tree: Module) -> str:
    # TODO why this fails?
    # validator.visit(tree)

    fix_missing_locations(tree)
    generated_code = unparse(tree)
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


def derived_resources_class(project_id: str, parameters: List[str]) -> str:
    tree = Module(body=[])

    # TODO avoid having "arcor2.resources" as string - how?
    add_import(tree, "arcor2.resources", ResourcesBase.__name__)

    derived_cls_name = "Resources"

    init_body: List = [Expr(value=Call(
        func=Attribute(value=Call(func=Name(id='super', ctx=Load()),
                                  args=[Name(id=derived_cls_name, ctx=Load()),
                                        Name(id='self', ctx=Load())], keywords=[]),
                       attr='__init__', ctx=Load()), args=[Str(s=project_id)],
        keywords=[]))]

    for param in parameters:
        init_body.append(Assign(targets=[Attribute(value=Name(id='self', ctx=Load()), attr="_" + param, ctx=Store())],
                                value=Call(
                                    func=Attribute(value=Name(id='self', ctx=Load()), attr='parameters', ctx=Load()),
                                    args=[Str(s=param)], keywords=[])))

    cls_def = ClassDef(name=derived_cls_name,
                       bases=[Name(id=ResourcesBase.__name__, ctx=Load())],
                       keywords=[],
                       body=[FunctionDef(name='__init__', args=arguments(args=[arg(arg='self', annotation=None)],
                                                                         vararg=None, kwonlyargs=[],
                                                                         kw_defaults=[], kwarg=None,
                                                                         defaults=[]), body=init_body,
                                         decorator_list=[], returns=None)], decorator_list=[])

    tree.body.append(cls_def)

    for param in parameters:
        cls_def.body.append(FunctionDef(
            name=param,
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
                    func=Attribute(
                        value=Name(
                            id='Resources',
                            ctx=Load()),
                        attr='print_info',
                        ctx=Load()),
                    args=[
                        Str(
                            s=param,
                            kind=''),
                        Attribute(
                            value=Name(
                                id='self',
                                ctx=Load()),
                            attr='_' + param,
                            ctx=Load())],
                    keywords=[])),
                Return(value=Attribute(
                    value=Name(
                        id='self',
                        ctx=Load()),
                    attr='_' + param,
                    ctx=Load()))],
            decorator_list=[Name(
                id='property',
                ctx=Load())],
            returns=None,
            type_comment=None))

    return tree_to_str(tree)


def dump(tree: Module) -> None:
    return typed_astunparse.dump(tree)
