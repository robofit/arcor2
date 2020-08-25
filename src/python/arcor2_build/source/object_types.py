from typed_ast.ast3 import AnnAssign, Assign, Index, Load, Module, Name, Store, Str, Subscript

from arcor2.helpers import camel_case_to_snake_case
from arcor2.source.utils import find_function, get_name_attr


def fix_object_name(object_id: str) -> str:

    return camel_case_to_snake_case(object_id).replace(" ", "_")


def object_instance_from_res(tree: Module, object_name: str, object_id: str, cls_name: str) -> None:

    main_body = find_function("main", tree).body
    last_assign_idx = -1

    for body_idx, body_item in enumerate(main_body):

        if isinstance(body_item, (Assign, AnnAssign)):
            last_assign_idx = body_idx

    assign = AnnAssign(
        target=Name(id=fix_object_name(object_name), ctx=Store()),
        annotation=Name(id=cls_name, ctx=Load()),
        value=Subscript(
            value=get_name_attr("res", "objects"), slice=Index(value=Str(s=object_id, kind="")), ctx=Load()
        ),
        simple=1,
    )

    main_body.insert(last_assign_idx + 1, assign)
