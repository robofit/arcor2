import pytest

from arcor2.data.common import NamedOrientation, Orientation
from arcor2.exceptions import Arcor2Exception


def test_valid_orientation() -> None:

    o1 = Orientation(0, 0, 0, 1)
    o2 = Orientation()
    o2.set_from_quaternion(o1.as_quaternion())
    assert o1 == o2


def test_invalid_orientation() -> None:

    with pytest.raises(Arcor2Exception):
        Orientation(0, 0, 0, 0)

    o = Orientation()
    o.w = 0

    with pytest.raises(Arcor2Exception):
        o.as_quaternion()


def test_id_stuff() -> None:

    no = NamedOrientation("name", Orientation())
    assert no.id

    no_copy = no.copy()
    assert no_copy.id

    assert no.id != no_copy.id
