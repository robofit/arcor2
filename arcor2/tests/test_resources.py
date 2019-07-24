# -*- coding: utf-8 -*-

import pytest  # type: ignore

from arcor2.resources import IntResources, ResourcesException
from arcor2.source.tests.test_logic import VALID_PROJECT, VALID_PROJECT_WO_LOGIC, VALID_SCENE
from arcor2.data import ActionPoint


@pytest.fixture
def res():

    IntResources.CUSTOM_OBJECT_TYPES_MODULE = "arcor2.user_objects"
    res = IntResources(VALID_SCENE, VALID_PROJECT)
    return res


def test_parameters_existing_action(res):

    d = res.parameters("MoveToBoxIN")
    assert "end_effector" in d
    assert "target" in d
    assert "speed" in d


def test_parameters_non_existing_action(res):

    with pytest.raises(ResourcesException):
        res.parameters("NonSense")


def test_action_point_existing(res):

    ap = res.action_point("BoxIN", "transfer")
    assert isinstance(ap, ActionPoint)


def test_action_point_confused(res):

    with pytest.raises(ResourcesException):
        res.action_point("BoxIN", "input")


def test_action_point_non_existing(res):

    with pytest.raises(ResourcesException):
        res.action_point("foo", "bar")
