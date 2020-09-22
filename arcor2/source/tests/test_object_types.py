from arcor2.data.object_type import ObjectTypeMeta
from arcor2.source.object_types import check_object_type, new_object_type_source


def test_meta_to_source() -> None:

    parent = ObjectTypeMeta(type="Generic")
    child = ObjectTypeMeta(type="NewType", description="blabla bla", base="Generic")

    source = new_object_type_source(parent, child)
    check_object_type(source, "NewType")
