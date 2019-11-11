from arcor2.data.object_type import ObjectTypeMeta
from arcor2.source.object_types import new_object_type_source, check_object_type


def test_meta_to_source():

    parent = ObjectTypeMeta(type="Generic")
    child = ObjectTypeMeta(type="NewType", description="blabla bla", base="Generic")

    source = new_object_type_source(parent, child)
    check_object_type(source, "NewType")
