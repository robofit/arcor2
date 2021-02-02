from typed_ast.ast3 import AnnAssign, Index, Load, Name, Store, Str, Subscript

from arcor2.exceptions import Arcor2Exception
from arcor2.helpers import is_valid_identifier, is_valid_type
from arcor2.source.utils import get_name_attr


def object_instance_from_res(object_name: str, object_id: str, cls_name: str) -> AnnAssign:

    if not is_valid_identifier(object_name):
        raise Arcor2Exception(f"Object name {object_name} is not a valid identifier.")

    if not is_valid_type(cls_name):
        raise Arcor2Exception(f"Class name {cls_name} is not valid.")

    return AnnAssign(
        target=Name(id=object_name, ctx=Store()),
        annotation=Name(id=cls_name, ctx=Load()),
        value=Subscript(
            value=get_name_attr("res", "objects"), slice=Index(value=Str(s=object_id, kind="")), ctx=Load()
        ),
        simple=1,
    )
