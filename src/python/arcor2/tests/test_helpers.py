import pytest

from arcor2 import helpers as hlp


@pytest.mark.parametrize(
    "val",
    [
        "valid",
        "valid_ident",
        "abc",
        pytest.param("InvalidIdent", marks=pytest.mark.xfail),
        pytest.param("invalid ident", marks=pytest.mark.xfail),
        pytest.param("invalid?ident", marks=pytest.mark.xfail),
        pytest.param("Abc", marks=pytest.mark.xfail),
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
        pytest.param("invalid_type", marks=pytest.mark.xfail),
        pytest.param("Invalid Type", marks=pytest.mark.xfail),
        pytest.param("invalid?type", marks=pytest.mark.xfail),
        pytest.param("abc", marks=pytest.mark.xfail),
    ],
)
def test_is_valid_type(val) -> None:
    assert hlp.is_valid_type(val)
