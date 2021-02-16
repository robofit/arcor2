import pytest

from arcor2 import helpers as hlp


@pytest.mark.parametrize(
    "val",
    [
        "valid",
        "valid_ident",
        "abc",
        "InvalidIdent",
        pytest.param("invalid ident", marks=pytest.mark.xfail),
        pytest.param("invalid?ident", marks=pytest.mark.xfail),
        "Abc",
        pytest.param("def", marks=pytest.mark.xfail),
        pytest.param("class", marks=pytest.mark.xfail),
    ],
)
def test_is_valid_identifier(val) -> None:
    assert hlp.is_valid_identifier(val)


@pytest.mark.parametrize(
    "val",
    [
        "Valid",
        "ValidType",
        "invalid_type",
        pytest.param("Invalid Type", marks=pytest.mark.xfail),
        pytest.param("invalid?type", marks=pytest.mark.xfail),
        "abc",
    ],
)
def test_is_valid_type(val) -> None:
    assert hlp.is_valid_type(val)
