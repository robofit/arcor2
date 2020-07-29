from arcor2.data.object_type import ObjectTypeMeta
from arcor2.source.object_types import new_object_type
from arcor2.source.utils import tree_to_str


def test_meta_to_source() -> None:

    parent = ObjectTypeMeta(type="Generic")
    child = ObjectTypeMeta(type="NewType", description="blabla bla", base="Generic")

    source = tree_to_str(new_object_type(parent, child))

    assert "class NewType(Generic)" in source
