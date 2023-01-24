import numpy as np
import pytest

from arcor2_kinect_azure_data.joint import InvalidConfidence, InvalidMeasurement, JointConfidence, JointValid


def test_joint_confidence_valid() -> None:
    joint = np.array([0, 0, 0, 0, 0, 0, 0, 1, 0])
    jc = JointConfidence.from_joint(joint)

    assert jc == JointConfidence.LOW


def test_joint_confidence_invalid() -> None:
    joint = np.array([0, 0, 0, 0, 0, 0, 0, -1, 0, 0, 0])

    with pytest.raises(InvalidConfidence) as exc_info:
        JointConfidence.from_joint(joint)
    assert exc_info.value.args[0] == "Confidence joint value -1 is invalid"

    joint = np.array([0, 0, 0, 0, 0, 0, 0, 4, 0, 0, 0])

    with pytest.raises(InvalidConfidence) as exc_info:
        JointConfidence.from_joint(joint)
    assert exc_info.value.args[0] == "Confidence joint value 4 is invalid"


def test_joint_valid_valid() -> None:
    joint = np.array([0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1])
    jv = JointValid.from_joint(joint)

    assert jv == JointValid.VALID


def test_joint_valid_invalid() -> None:
    joint = np.array([0, 0, 0, 0, 0, 0, 0, 0, 0, 0, -1])

    with pytest.raises(InvalidMeasurement) as exc_info:
        JointValid.from_joint(joint)
    assert exc_info.value.args[0] == "Got invalid joint value for field 'valid': -1"

    joint = np.array([0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 2])

    with pytest.raises(InvalidMeasurement) as exc_info:
        JointValid.from_joint(joint)
    assert exc_info.value.args[0] == "Got invalid joint value for field 'valid': 2"
