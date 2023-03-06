import importlib
import os
import sys

from arcor2.cached import CachedProject
from arcor2.data.common import (
    ActionPoint,
    Joint,
    NamedOrientation,
    Orientation,
    Pose,
    Position,
    Project,
    ProjectRobotJoints,
)
from arcor2_build.source.utils import global_action_points_class


class SimResources:
    def __init__(self, proj: CachedProject) -> None:
        self.project = proj


def test_global_aps_cls() -> None:
    proj = Project("test", "scene_id")

    pos = Position(1, 2, 3)
    ap1 = ActionPoint("ap1", pos)
    ap1_o1 = NamedOrientation("o1", Orientation(0.707, 0, 0, 0.707))
    ap1.orientations.append(ap1_o1)
    ap1_j1 = ProjectRobotJoints("j1", "robot", [Joint("whatever", 1234)])
    ap1.robot_joints.append(ap1_j1)
    proj.action_points.append(ap1)

    os.environ["ARCOR2_PROJECT_PATH"] = "/tmp"
    import arcor2_runtime.resources  # noqa

    my_name = "my_module"
    my_spec = importlib.util.spec_from_loader(my_name, loader=None)
    assert my_spec
    my_module = importlib.util.module_from_spec(my_spec)

    cproj = CachedProject(proj)

    src = global_action_points_class(cproj)
    exec(src, my_module.__dict__)
    sys.modules["my_module"] = my_module

    aps = my_module.ActionPoints(SimResources(cproj))

    assert aps.ap1.position == pos
    assert aps.ap1.position is not pos

    assert aps.ap1.poses.o1 == Pose(ap1.position, ap1_o1.orientation)
    assert aps.ap1.poses.o1.orientation is not ap1_o1.orientation

    assert aps.ap1.joints.j1 == ap1_j1
    assert aps.ap1.joints.j1 is not ap1_j1
