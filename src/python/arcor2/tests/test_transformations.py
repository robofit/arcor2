import copy
from math import cos, pi, sin, sqrt

import numpy as np
import pytest

from arcor2.cached import CachedProject, CachedScene
from arcor2.data.common import ActionPoint, Orientation, Pose, Position, Project, Scene, SceneObject
from arcor2.exceptions import Arcor2Exception
from arcor2.transformations import (
    get_parent_pose,
    make_global_ap_relative,
    make_pose_abs,
    make_pose_rel,
    make_relative_ap_global,
)


def random_pose() -> Pose:
    return Pose(random_position(), random_orientation())


def random_position() -> Position:
    x, y, z = np.random.random(3) * 2 - 1
    return Position(x, y, z)


def random_orientation() -> Orientation:

    r1, r2, r3 = np.random.random(3)

    q1 = sqrt(1.0 - r1) * (sin(2 * pi * r2))
    q2 = sqrt(1.0 - r1) * (cos(2 * pi * r2))
    q3 = sqrt(r1) * (sin(2 * pi * r3))
    q4 = sqrt(r1) * (cos(2 * pi * r3))

    return Orientation(q1, q2, q3, q4)


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


def test_make_pose_abs_4() -> None:

    parent = Pose()
    child = Pose()
    assert make_pose_abs(parent, child) == parent


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


@pytest.mark.repeat(100)
def test_make_pose_rel_and_abs_again_random() -> None:

    # hierarchy of poses
    p1 = random_pose()
    p2 = random_pose()
    p3 = random_pose()

    # global pose
    c = random_pose()

    # make it relative
    c1 = make_pose_rel(p1, c)  # c1 = c relative to p1
    c2 = make_pose_rel(p2, c1)  # c2 = c relative to p2
    c3 = make_pose_rel(p3, c2)  # c3 = c relative to p3

    # make it absolute again
    cc2 = make_pose_abs(p3, c3)
    assert cc2 == c2

    cc1 = make_pose_abs(p2, cc2)
    assert cc1 == c1

    cc = make_pose_abs(p1, cc1)
    assert cc == c


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

    assert ap3.parent
    ap3_parent = get_parent_pose(cached_scene, cached_project, ap3.parent)

    assert Pose(ap2.position, Orientation()) == ap3_parent.pose
    assert ap3_parent.parent_id == ap1.id

    make_relative_ap_global(cached_scene, cached_project, ap3)

    assert ap3.parent is None
    assert ap3.position.x == 0.0  # type: ignore

    make_global_ap_relative(cached_scene, cached_project, ap3, ap2.id)

    assert ap3.parent == ap2.id
    assert ap3.position.x == -1

    ap3.parent = "something_unknown"

    with pytest.raises(Arcor2Exception):
        make_relative_ap_global(cached_scene, cached_project, ap3)
