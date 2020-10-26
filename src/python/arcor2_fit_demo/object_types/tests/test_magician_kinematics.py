import pytest

from arcor2.data.common import Orientation, Pose, Position
from arcor2_fit_demo.object_types.abstract_dobot import DobotException, DobotSettings
from arcor2_fit_demo.object_types.dobot_magician import DobotMagician


@pytest.mark.parametrize(
    "pose",
    [
        Pose(
            Position(0.21153890915642332, -0.015862009362322887, -0.03703723907470703),
            Orientation(-2.031830665648833e-12, 1.0, -1.2441374605481395e-28, 6.123233995736766e-17),
        ),
        Pose(
            Position(0.3139496261294276, -0.02310362993117364, -0.06997747802734375),
            Orientation(-2.031830665648833e-12, 1.0, -1.2441374605481395e-28, 6.123233995736766e-17),
        ),
        Pose(
            Position(0.21878252578561824, -0.03278912729933825, 0.08210411071777343),
            Orientation(-2.031830665648833e-12, 1.0, -1.2441374605481395e-28, 6.123233995736766e-17),
        ),
        Pose(
            Position(-0.019879645332372506, -0.26511857503275366, -0.05548677825927734),
            Orientation(-2.031830665648833e-12, 1.0, -1.2441374605481395e-28, 6.123233995736766e-17),
        ),
    ],
)
def test_ik_fk(pose) -> None:

    dm = DobotMagician("id", "name", Pose(), DobotSettings(simulator=True))
    joints = dm.inverse_kinematics("", pose)
    comp_pose = dm.forward_kinematics("", joints)
    assert pose == comp_pose


@pytest.mark.parametrize(
    "pose",
    [
        Pose(
            Position(0.18858207843346286, -0.25930897734383396, -0.1476832733154297),
            Orientation(-2.031830665648833e-12, 1.0, -1.2441374605481395e-28, 6.123233995736766e-17),
        ),
        Pose(
            Position(0.10383602529228289, -0.009138188297509139, -0.058923263549804684),
            Orientation(-2.031830665648833e-12, 1.0, -1.2441374605481395e-28, 6.123233995736766e-17),
        ),
    ],
)
def test_ik_fk_invalid(pose) -> None:

    dm = DobotMagician("id", "name", Pose(), DobotSettings(simulator=True))
    with pytest.raises(DobotException):
        dm.inverse_kinematics("", pose)
