import os

import pytest

from arcor2.data.common import Orientation, Pose, Position
from arcor2_fit_demo.object_types.abstract_dobot import DobotException, DobotSettings
from arcor2_fit_demo.object_types.dobot_magician import DobotMagician

URL = os.getenv("ARCOR2_DOBOT_URL", "http://localhost:5018")


@pytest.mark.skip(reason="Temporarily disabled (need to run the service).")
@pytest.mark.parametrize(
    "pose",
    [
        Pose(
            Position(0.24027805415562356, -0.033064804793467024, -0.10107283020019531),
            Orientation(-0.06832257459695434, 0.9976632827765306, -4.18355111448332e-18, 6.108925729395595e-17),
        ),
        Pose(
            Position(0.2570099061465494, -0.03512534022111209, 0.021290023803710936),
            Orientation(-0.0678616466931505, 0.9976947413453146, -4.155327420381767e-18, 6.10911835757343e-17),
        ),
        Pose(
            Position(0.21265726282945766, -0.04578391051491453, 0.10375743103027343),
            Orientation(-0.10583019614908788, 0.9943842162781173, -6.480230548355851e-18, 6.088847237938229e-17),
        ),
        Pose(
            Position(-0.025881654316776154, -0.30372793589135566, -0.14060073852539062),
            Orientation(-0.7365139137143566, 0.6764223938525108, -4.5098470347888836e-17, 4.1418925975153384e-17),
        ),
        Pose(
            Position(0.13336894808429914, 0.20994138623435366, 0.013065299987792975),
            Orientation(0.48155122629938013, 0.8764179462160523, 2.948650839565093e-17, 5.366512162743928e-17),
        ),
    ],
)
def test_ik_fk(pose) -> None:

    dm = DobotMagician("id", "name", Pose(), DobotSettings(URL))
    joints = dm.inverse_kinematics("", pose)
    comp_pose = dm.forward_kinematics("", joints)
    assert pose == comp_pose


@pytest.mark.skip(reason="Temporarily disabled (need to run the service).")
@pytest.mark.parametrize(
    "pose",
    [
        Pose(
            Position(0.3276530250942208, -0.019854417803022214, -0.12388809204101563),
            Orientation(-0.03025631115266017, 0.9995421730149426, -1.852664730355582e-18, 6.120430613977697e-17),
        ),
        Pose(
            Position(0.033229495834859415, -0.09794051686171329, -0.059101608276367186),
            Orientation(-0.5825403102921434, 0.8128018127961659, -3.5670306318678966e-17, 4.976975691909954e-17),
        ),
    ],
)
def test_ik_fk_out_of_reach(pose) -> None:

    dm = DobotMagician("id", "name", Pose(), DobotSettings(URL))
    with pytest.raises(DobotException):
        dm.inverse_kinematics("", pose)


@pytest.mark.skip(reason="Temporarily disabled (need to run the service).")
@pytest.mark.parametrize(
    "pose",
    [
        Pose(
            Position(0.24027805415562356, -0.033064804793467024, -0.10107283020019531),
            Orientation(-0.06832257459695434, -4.18355111448332e-18, 0.9976632827765306, 6.108925729395595e-17),
        ),
        Pose(
            Position(0.2570099061465494, -0.03512534022111209, 0.021290023803710936),
            Orientation(-0.0678616466931505, 6.10911835757343e-17, -4.155327420381767e-18, 0.9976947413453146),
        ),
    ],
)
def test_ik_fk_impossible_orientation(pose) -> None:

    dm = DobotMagician("id", "name", Pose(), DobotSettings(URL))
    with pytest.raises(DobotException, match="Impossible orientation."):
        dm.inverse_kinematics("", pose)
