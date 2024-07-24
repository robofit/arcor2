import pytest

from arcor2.data.common import Pose
from arcor2.rest import RestException
from arcor2_ur.object_types.ur5e import Ur5e, UrSettings
from arcor2_ur.tests.conftest import Urls


@pytest.mark.timeout(30)
def test_basics(start_processes: Urls) -> None:
    ot = Ur5e("", "", Pose(), UrSettings(start_processes.robot_url))

    assert len(ot.robot_joints()) == 6
    pos = ot.get_end_effector_pose("")
    pos.position.z -= 0.01
    ot.move_to_pose("", pos, 0.5)

    with pytest.raises(RestException):  # TODO stopping the service is broken ATM (Segmentation Fault)
        ot.cleanup()
