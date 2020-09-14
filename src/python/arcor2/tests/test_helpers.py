import datetime

import pytest  # type: ignore

from arcor2 import helpers as hlp


def test_import_cls_valid() -> None:

    mod, cls = hlp.import_cls("datetime/timedelta")

    assert mod == datetime
    assert cls == datetime.timedelta


def test_import_cls_non_existing() -> None:

    with pytest.raises(hlp.ImportClsException):

        mod, cls = hlp.import_cls("nonsense/NonSense")


def test_import_cls_invalid() -> None:

    with pytest.raises(hlp.ImportClsException):

        mod, cls = hlp.import_cls("Generic")


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
