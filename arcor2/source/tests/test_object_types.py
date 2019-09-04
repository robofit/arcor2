from arcor2.data.object_type import ObjectTypeMeta
from arcor2.source.object_types import new_object_type_source, object_type_meta, get_object_actions


def test_meta_to_source_and_back():

    parent = ObjectTypeMeta(type="Generic")
    child = ObjectTypeMeta(type="NewType", description="blabla bla", base="Generic")

    source = new_object_type_source(parent, child)

    meta_from_source = object_type_meta(source)
    assert child == meta_from_source

    actions = get_object_actions(source)
    assert not actions
