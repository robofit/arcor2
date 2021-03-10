# -*- coding: utf-8 -*-

import copy

import pytest
import quaternion

from arcor2.cached import CachedProject, CachedScene
from arcor2.data.common import ActionPoint, Orientation, Pose, Position, Project, Scene, SceneObject
from arcor2.exceptions import Arcor2Exception
from arcor2.transformations import (
    make_global_ap_relative,
    make_orientation_abs,
    make_orientation_rel,
    make_pose_abs,
    make_pose_rel,
    make_relative_ap_global,
)


def test_make_pose_rel() -> None:

    parent = Pose(Position(1, 2, 3), Orientation(0, 0, 1, 0))
    child_to_be = copy.deepcopy(parent)
    assert make_pose_rel(parent, child_to_be) == Pose()


def test_make_pose_abs() -> None:

    parent = Pose(Position(1, 2, 3), Orientation(0, 0, 1, 0))
    child = Pose()
    assert make_pose_abs(parent, child) == parent


def test_make_pose_abs_2() -> None:

    parent = Pose(Position(-1, 2, -3), Orientation(0, 0.707, -0.707, 0))
    child = Pose()
    assert make_pose_abs(parent, child) == parent


def test_make_pose_abs_3() -> None:

    parent = Pose(Position(1, 1, 0), Orientation(0, 0, 0.707, 0.707))
    child = Pose(Position(-1, 1, 0), Orientation())
    assert make_pose_abs(parent, child) == Pose(Position(0, 0, 0), Orientation(0, 0, 0.707, 0.707))


def test_make_pose_rel_and_abs_again() -> None:

    parent = Pose(Position(), Orientation(0, 0, 1, 0))
    child_to_be = Pose(Position(1, 0, 0))
    child = make_pose_rel(parent, child_to_be)
    assert child == Pose(Position(-1, 0, 0), Orientation(0, 0, -1, 0))
    assert make_pose_abs(parent, child) == child_to_be


def test_make_pose_rel_and_abs_again_2() -> None:

    parent = Pose(Position(-1, 1, -1), Orientation(0, -0.707, 0.707, 0))
    child_to_be = Pose(Position(10, -10, 3))
    child = make_pose_rel(parent, child_to_be)
    assert make_pose_abs(parent, child) == child_to_be


def test_make_orientation_abs_2() -> None:

    parent = Orientation(0, 0, 0, 1)
    child = Orientation(1, 0, 0, 0)
    assert make_orientation_abs(parent, child) == child


def test_make_orientation_abs_3() -> None:

    parent = Orientation(0, 1, 0, 0)
    child = Orientation(0, 0, 0, 1)
    assert make_orientation_abs(parent, child) == parent


def test_make_orientation_rel() -> None:

    parent = Orientation(0.707, 0, 0.707, 0)
    child = Orientation(0.707, 0, 0.707, 0)
    assert make_orientation_rel(parent, child) == Orientation(0, 0, 0, 1)


def test_make_orientation_rel_2() -> None:

    parent = Orientation(0, 0, 0, 1)
    child = Orientation()
    child.set_from_quaternion(quaternion.from_euler_angles(0.123, 0.345, 0.987))
    assert make_orientation_rel(parent, child) == child


def test_make_orientation_rel_and_then_again_abs() -> None:

    parent = Orientation(0, -1, 0, 0)
    obj = Orientation(0.707, 0, 0.707, 0)

    rel_obj = make_orientation_rel(parent, obj)
    assert obj == make_orientation_abs(parent, rel_obj)


def test_make_orientation_rel_and_then_again_abs_2() -> None:

    parent = Orientation()
    parent.set_from_quaternion(quaternion.from_euler_angles(1.25, -2, 3.78))
    obj = Orientation()
    obj.set_from_quaternion(quaternion.from_euler_angles(-2.2, 4, 1.9))

    rel_obj = make_orientation_rel(parent, obj)
    assert obj == make_orientation_abs(parent, rel_obj)


def test_make_relative_ap_global_and_relative_again() -> None:

    scene = Scene("s1")
    so1 = SceneObject("so1", "WhatEver", Pose(Position(3, 0, 0), Orientation()))
    scene.objects.append(so1)
    cached_scene = CachedScene(scene)

    project = Project("p1", scene.id)
    ap1 = ActionPoint("ap1", Position(-1, 0, 0), parent=so1.id)
    project.action_points.append(ap1)
    ap2 = ActionPoint("ap2", Position(-1, 0, 0), parent=ap1.id)
    project.action_points.append(ap2)
    ap3 = ActionPoint("ap3", Position(-1, 0, 0), parent=ap2.id)
    project.action_points.append(ap3)

    cached_project = CachedProject(project)

    make_relative_ap_global(cached_scene, cached_project, ap3)

    assert ap3.parent is None
    assert ap3.position.x == 0.0

    make_global_ap_relative(cached_scene, cached_project, ap3, ap2.id)

    assert ap3.parent == ap2.id
    assert ap3.position.x == -1

    ap3.parent = "something_unknown"

    with pytest.raises(Arcor2Exception):
        make_relative_ap_global(cached_scene, cached_project, ap3)
