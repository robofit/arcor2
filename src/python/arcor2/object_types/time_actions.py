import time
from typing import Optional

from arcor2.data.common import ActionMetadata
from arcor2.object_types.abstract import Generic, Settings


class TimeActions(Generic):
    """Time-related actions."""

    _ABSTRACT = False

    def __init__(self, obj_id: str, name: str, settings: Optional[Settings] = None) -> None:
        super(TimeActions, self).__init__(obj_id, name, settings)
        self._last_time: Optional[float] = None

    def sleep(self, seconds: float = 1.0, *, an: Optional[str] = None) -> None:

        assert 0.0 <= seconds <= 10.0e6

        time.sleep(seconds)

    def rate(self, period: float = 1.0, *, an: Optional[str] = None) -> None:
        """Can be used to maintain desired rate of the loop. Should be the
        first action.

        :param period: Desired period in seconds.
        :return:
        """

        assert 0.0 <= period <= 10.0e6

        now = time.monotonic()

        if self._last_time is not None:

            dif = self._last_time + period - now

            if dif > 0:
                time.sleep(dif)

        self._last_time = now

    def time_ns(self, *, an: Optional[str] = None) -> int:
        """Returns nanoseconds since Unix Epoch.

        :return:
        """
        return time.time_ns()

    sleep.__action__ = ActionMetadata(blocking=True)  # type: ignore
    rate.__action__ = ActionMetadata(blocking=True)  # type: ignore
    time_ns.__action__ = ActionMetadata(blocking=True)  # type: ignore
