from contextlib import nullcontext as does_not_raise

import pytest

from arcor2 import helpers as hlp
from arcor2.exceptions import Arcor2Exception


@pytest.mark.parametrize(
    ("val", "expectation"),
    [
        ("_valid", does_not_raise()),
        ("v_a_l_i_d_", does_not_raise()),
        ("valid", does_not_raise()),
        ("valid_ident", does_not_raise()),
        ("abc", does_not_raise()),
        ("InvalidIdent", does_not_raise()),
        ("Abc", does_not_raise()),
        ("a", does_not_raise()),
        ("inv ", pytest.raises(Arcor2Exception)),
        ("1inv", pytest.raises(Arcor2Exception)),
        ("invalid ident", pytest.raises(Arcor2Exception)),
        ("invalid?ident", pytest.raises(Arcor2Exception)),
        ("def", pytest.raises(Arcor2Exception)),
        ("class", pytest.raises(Arcor2Exception)),
        ("print", pytest.raises(Arcor2Exception)),
        ("int", pytest.raises(Arcor2Exception)),
        ("id", pytest.raises(Arcor2Exception)),
        ("1", pytest.raises(Arcor2Exception)),
        (":", pytest.raises(Arcor2Exception)),
    ],
)
def test_is_valid_identifier(val, expectation) -> None:
    with expectation:
        hlp.is_valid_identifier(val)
