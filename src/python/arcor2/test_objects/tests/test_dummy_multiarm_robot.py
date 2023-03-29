from arcor2.test_objects.dummy_multiarm_robot import DummyMultiArmRobot


def test_dmar() -> None:
    assert not DummyMultiArmRobot.abstract()
