# -*- coding: utf-8 -*-

import datetime

import pytest  # type: ignore

from arcor2.helpers import import_cls, ImportClsException, convert_cc, get_actions_cache
from arcor2.source.tests.test_logic import VALID_PROJECT, VALID_PROJECT_WO_LOGIC
from arcor2.data import Project


def test_import_cls_valid():

    mod, cls = import_cls("datetime/timedelta")

    assert mod == datetime
    assert cls == datetime.timedelta


def test_import_cls_non_existing():

    with pytest.raises(ImportClsException):

        mod, cls = import_cls("nonsense/NonSense")


def test_import_cls_invalid():

    with pytest.raises(ImportClsException):

        mod, cls = import_cls("Generic")


def test_convert_cc():

    assert convert_cc("camelCase") == "camel_case"


def test_get_actions_cache_w_logic():

    cache, first, last = get_actions_cache(VALID_PROJECT)

    assert len(cache) == 3
    assert first
    assert last
    assert "MoveToBoxIN" in cache
    assert "MoveToTester" in cache
    assert "MoveToBoxOUT" in cache


def test_get_actions_cache_wo_logic():

    cache, first, last = get_actions_cache(VALID_PROJECT_WO_LOGIC)

    assert len(cache) == 3
    assert first is None
    assert last is None


def test_get_actions_cache_empty_project():

    proj = Project("proj", "scene")

    cache, first, last = get_actions_cache(proj)

    assert not cache
    assert first is None
    assert last is None
