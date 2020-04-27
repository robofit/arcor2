# -*- coding: utf-8 -*-

import datetime
import copy
import quaternion  # type: ignore

import pytest  # type: ignore

from arcor2 import helpers as hlp
from arcor2.data.common import Orientation, Pose, Position


def test_make_pose_rel():

    parent = Pose(Position(1, 2, 3), Orientation(0, 0, 1, 0))
    child_to_be = copy.deepcopy(parent)
    assert hlp.make_pose_rel(parent, child_to_be) == Pose()


def test_make_pose_abs():

    parent = Pose(Position(1, 2, 3), Orientation(0, 0, 1, 0))
    child = Pose()
    assert hlp.make_pose_abs(parent, child) == parent


def test_make_pose_abs_2():

    parent = Pose(Position(-1, 2, -3), Orientation(0, 0.707, -0.707, 0))
    child = Pose()
    assert hlp.make_pose_abs(parent, child) == parent


def test_make_pose_abs_3():

    parent = Pose(Position(1, 1, 0), Orientation(0, 0, 0.707, 0.707))
    child = Pose(Position(-1, 1, 0), Orientation())
    assert hlp.make_pose_abs(parent, child) == Pose(Position(0, 0, 0), Orientation(0, 0, 0.707, 0.707))


def test_make_pose_rel_and_abs_again():

    parent = Pose(Position(), Orientation(0, 0, 1, 0))
    child_to_be = Pose(Position(1, 0, 0))
    child = hlp.make_pose_rel(parent, child_to_be)
    assert child == Pose(Position(-1, 0, 0), Orientation(0, 0, -1, 0))
    assert hlp.make_pose_abs(parent, child) == child_to_be


def test_make_pose_rel_and_abs_again_2():

    parent = Pose(Position(-1, 1, -1), Orientation(0, -0.707, 0.707, 0))
    child_to_be = Pose(Position(10, -10, 3))
    child = hlp.make_pose_rel(parent, child_to_be)
    assert hlp.make_pose_abs(parent, child) == child_to_be


def test_make_orientation_abs_2():

    parent = Orientation(0, 0, 0, 1)
    child = Orientation(1, 0, 0, 0)
    assert hlp.make_orientation_abs(parent, child) == child


def test_make_orientation_abs_3():

    parent = Orientation(0, 1, 0, 0)
    child = Orientation(0, 0, 0, 1)
    assert hlp.make_orientation_abs(parent, child) == parent


def test_make_orientation_rel():

    parent = Orientation(0.707, 0, 0.707, 0)
    child = Orientation(0.707, 0, 0.707, 0)
    assert hlp.make_orientation_rel(parent, child) == Orientation(0, 0, 0, 1)


def test_make_orientation_rel_2():

    parent = Orientation(0, 0, 0, 1)
    child = Orientation()
    child.set_from_quaternion(quaternion.from_euler_angles(0.123, 0.345, 0.987))
    assert hlp.make_orientation_rel(parent, child) == child


def test_make_orientation_rel_and_then_again_abs():

    parent = Orientation(0, -1, 0, 0)
    obj = Orientation(0.707, 0, 0.707, 0)

    rel_obj = hlp.make_orientation_rel(parent, obj)
    assert obj == hlp.make_orientation_abs(parent, rel_obj)


def test_make_orientation_rel_and_then_again_abs_2():

    parent = Orientation()
    parent.set_from_quaternion(quaternion.from_euler_angles(1.25, -2, 3.78))
    obj = Orientation()
    obj.set_from_quaternion(quaternion.from_euler_angles(-2.2, 4, 1.9))

    rel_obj = hlp.make_orientation_rel(parent, obj)
    assert obj == hlp.make_orientation_abs(parent, rel_obj)


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
