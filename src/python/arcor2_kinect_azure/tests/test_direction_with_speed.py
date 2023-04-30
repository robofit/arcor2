from arcor2.data.common import Direction
from arcor2_kinect_azure.kinect.aggregation import DirectionWithSpeed


def test_is_faster_than_true() -> None:
    dws_1 = DirectionWithSpeed(Direction(1.0, 1.0, 1.0), 1.1)
    dws_2 = DirectionWithSpeed(Direction(1.0, 1.0, 1.0), 1.0)

    is_faster = dws_1.is_faster_than(dws_2)

    assert is_faster is True


def test_is_faster_than_false() -> None:
    dws_1 = DirectionWithSpeed(Direction(1.0, 1.0, 1.0), 1.0)
    dws_2 = DirectionWithSpeed(Direction(2.0, 2.0, 2.0), 1.0)

    is_faster = dws_1.is_faster_than(dws_2)

    assert is_faster is False


def test_is_faster_than_true_differing_speed() -> None:
    dws_1 = DirectionWithSpeed(Direction(2.0, 2.0, 2.1), 2.0)
    dws_2 = DirectionWithSpeed(Direction(1.0, 1.0, 1.0), 1.0)

    is_faster = dws_1.is_faster_than(dws_2)

    assert is_faster is True


def test_is_faster_than_false_differing_speed() -> None:
    dws_1 = DirectionWithSpeed(Direction(3.0, 3.0, 3.0), 1.0)
    dws_2 = DirectionWithSpeed(Direction(1.0, 1.0, 1.1), 200.0)

    is_faster = dws_1.is_faster_than(dws_2)

    assert is_faster is False
