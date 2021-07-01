from typing import Optional

from arcor2 import rest
from arcor2.data.common import ActionMetadata

from .abstract_with_pose import AbstractWithPose


class Ict(AbstractWithPose):
    """REST interface to the ict service (0.4.0)."""

    _ABSTRACT = False

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
