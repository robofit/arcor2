from typing import Optional

from arcor2 import rest
from arcor2.data.common import ActionMetadata, Pose
from arcor2.data.object_type import Models

from .abstract_with_pose import AbstractWithPose, Settings


class Ict(AbstractWithPose):
    """REST interface to the ict service (0.1.0)."""

    _ABSTRACT = False

    # Init function because of parameter name "configurationId"
    # Should be removed after unifying of the patrameter name in all APIs
    def __init__(
        self,
        obj_id: str,
        name: str,
        pose: Pose,
        collision_model: Optional[Models] = None,
        settings: Optional[Settings] = None,
    ) -> None:
        super(AbstractWithPose, self).__init__(obj_id, name, pose, collision_model, settings)
        rest.call(
            rest.Method.PUT,
            f"{self.settings.url}/system/set",
            body=pose,
            params={"configurationId": self.settings.configuration_id, "id": self.id},
        )

    def test(self, serial_number: str, *, an: Optional[str] = None) -> bool:
        """Tests a PCB in an ICT tester.

        :return:
        """

        return rest.call(
            rest.Method.GET,
            f"{self.settings.url}/tester/test",
            params={"serialNumber": serial_number},
            return_type=bool,
        )

    def ready(self, *, an: Optional[str] = None) -> bool:
        """Determines whether the ICT Tester is open and ready to start
        testing.

        :return: True if ICT tester is ready; otherwise, false.
        """

        return rest.call(rest.Method.GET, f"{self.settings.url}/tester/ready", return_type=bool)

    test.__action__ = ActionMetadata(blocking=True)  # type: ignore
    ready.__action__ = ActionMetadata(blocking=True)  # type: ignore
