# -*- coding: utf-8 -*-

import datetime

import pytest  # type: ignore

from arcor2 import helpers as hlp


def test_import_cls_valid():

    mod, cls = hlp.import_cls("datetime/timedelta")

    assert mod == datetime
    assert cls == datetime.timedelta


def test_import_cls_non_existing():

    with pytest.raises(hlp.ImportClsException):

        mod, cls = hlp.import_cls("nonsense/NonSense")


def test_import_cls_invalid():

    with pytest.raises(hlp.ImportClsException):

        mod, cls = hlp.import_cls("Generic")


@pytest.mark.parametrize('input,output', [
     ("CamelCaseStr", "camel_case_str"),
     ("camelCaseStr", "camel_case_str"),
     ("camel_case_str", "camel_case_str"),
     ("Camel", "camel")
])
def test_camel_case_to_snake_case(input, output):
    assert hlp.camel_case_to_snake_case(input) == output


@pytest.mark.parametrize('input,output', [
    ("snake_case_str", "SnakeCaseStr"),
    ("SnakeCaseStr", "SnakeCaseStr"),
    ("snake", "Snake"),
    ("abc", "Abc")
])
def test_snake_case_to_camel_case(input, output):
    assert hlp.snake_case_to_camel_case(input) == output


@pytest.mark.parametrize('val', [
    "valid",
    "valid_ident",
    "abc",
    pytest.param("InvalidIdent", marks=pytest.mark.xfail),
    pytest.param("invalid ident", marks=pytest.mark.xfail),
    pytest.param("invalid?ident", marks=pytest.mark.xfail),
    pytest.param("Abc", marks=pytest.mark.xfail),
    pytest.param("def", marks=pytest.mark.xfail),
    pytest.param("class", marks=pytest.mark.xfail)
])
def test_is_valid_identifier(val):
    assert hlp.is_valid_identifier(val)


@pytest.mark.parametrize('val', [
    "Valid",
    "ValidType",
    pytest.param("invalid_type", marks=pytest.mark.xfail),
    pytest.param("Invalid Type", marks=pytest.mark.xfail),
    pytest.param("invalid?type", marks=pytest.mark.xfail),
    pytest.param("abc", marks=pytest.mark.xfail)
])
def test_is_valid_type(val):
    assert hlp.is_valid_type(val)
