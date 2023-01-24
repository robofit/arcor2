import numpy as np

from arcor2.data.common import Orientation, Position
from arcor2_kinect_azure_data.joint import BodyJoint, JointConfidence, JointValid


def test_body_joint() -> None:
    joint = np.array([1234, 1234, 1234, 1, 5678, 5678, 5678, 2, 0, 0, 1])

    body_joint = BodyJoint.from_joint(joint)

    assert body_joint.position == Position(1.234, 1.234, 1.234)
    assert body_joint.orientation == Orientation(5678.0, 5678.0, 5678.0, 1.0)
    assert body_joint.confidence_level == JointConfidence.MEDIUM
    assert body_joint.position_image_0 == 0
    assert body_joint.position_image_1 == 0
    assert body_joint.valid == JointValid.VALID
