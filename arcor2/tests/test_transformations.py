# -*- coding: utf-8 -*-

import copy

import quaternion  # type: ignore

from arcor2.data.common import Orientation, Pose, Position
from arcor2.transformations import make_orientation_abs, make_orientation_rel, make_pose_abs, make_pose_rel


def test_make_pose_rel():

    parent = Pose(Position(1, 2, 3), Orientation(0, 0, 1, 0))
    child_to_be = copy.deepcopy(parent)
    assert make_pose_rel(parent, child_to_be) == Pose()


def test_make_pose_abs():

    parent = Pose(Position(1, 2, 3), Orientation(0, 0, 1, 0))
    child = Pose()
    assert make_pose_abs(parent, child) == parent


def test_make_pose_abs_2():

    parent = Pose(Position(-1, 2, -3), Orientation(0, 0.707, -0.707, 0))
    child = Pose()
    assert make_pose_abs(parent, child) == parent


def test_make_pose_abs_3():

    parent = Pose(Position(1, 1, 0), Orientation(0, 0, 0.707, 0.707))
    child = Pose(Position(-1, 1, 0), Orientation())
    assert make_pose_abs(parent, child) == Pose(Position(0, 0, 0), Orientation(0, 0, 0.707, 0.707))


def test_make_pose_rel_and_abs_again():

    parent = Pose(Position(), Orientation(0, 0, 1, 0))
    child_to_be = Pose(Position(1, 0, 0))
    child = make_pose_rel(parent, child_to_be)
    assert child == Pose(Position(-1, 0, 0), Orientation(0, 0, -1, 0))
    assert make_pose_abs(parent, child) == child_to_be


def test_make_pose_rel_and_abs_again_2():

    parent = Pose(Position(-1, 1, -1), Orientation(0, -0.707, 0.707, 0))
    child_to_be = Pose(Position(10, -10, 3))
    child = make_pose_rel(parent, child_to_be)
    assert make_pose_abs(parent, child) == child_to_be


def test_make_orientation_abs_2():

    parent = Orientation(0, 0, 0, 1)
    child = Orientation(1, 0, 0, 0)
    assert make_orientation_abs(parent, child) == child


def test_make_orientation_abs_3():

    parent = Orientation(0, 1, 0, 0)
    child = Orientation(0, 0, 0, 1)
    assert make_orientation_abs(parent, child) == parent


def test_make_orientation_rel():

    parent = Orientation(0.707, 0, 0.707, 0)
    child = Orientation(0.707, 0, 0.707, 0)
    assert make_orientation_rel(parent, child) == Orientation(0, 0, 0, 1)


def test_make_orientation_rel_2():

    parent = Orientation(0, 0, 0, 1)
    child = Orientation()
    child.set_from_quaternion(quaternion.from_euler_angles(0.123, 0.345, 0.987))
    assert make_orientation_rel(parent, child) == child


def test_make_orientation_rel_and_then_again_abs():

    parent = Orientation(0, -1, 0, 0)
    obj = Orientation(0.707, 0, 0.707, 0)

    rel_obj = make_orientation_rel(parent, obj)
    assert obj == make_orientation_abs(parent, rel_obj)


def test_make_orientation_rel_and_then_again_abs_2():

    parent = Orientation()
    parent.set_from_quaternion(quaternion.from_euler_angles(1.25, -2, 3.78))
    obj = Orientation()
    obj.set_from_quaternion(quaternion.from_euler_angles(-2.2, 4, 1.9))

    rel_obj = make_orientation_rel(parent, obj)
    assert obj == make_orientation_abs(parent, rel_obj)
