from typing import FrozenSet, Optional
import time

from arcor2.services import Service
from arcor2.data.common import ActionMetadata
from arcor2.action import action


class TimeService(Service):
    """
    Time-related actions.
    """

    def __init__(self, configuration_id: str):  # TODO avoid need for configuration_id?
        super(TimeService, self).__init__(configuration_id)
        self._rate_start_time: Optional[float] = None

    @staticmethod
    def get_configuration_ids() -> FrozenSet[str]:
        return frozenset({"default"})

    @action
    def sleep(self, seconds: float = 1.0) -> None:

        assert 0.0 <= seconds <= 10.0e6

        time.sleep(seconds)

    @action
    def rate(self, period: float = 1.0) -> None:
        """
        Can be used to maintain desired rate of the loop. Should be the first action.
        :param period: Desired period in seconds.
        :return:
        """

        assert 0.0 <= period <= 10.0e6

        now = time.monotonic()

        if self._rate_start_time is None:
            self._rate_start_time = now
            return

        dif = self._rate_start_time + period - now

        if dif > 0:
            time.sleep(dif)

    @action
    def time_ns(self) -> int:
        """
        Returns nanoseconds since Unix Epoch.
        :return:
        """
        return time.time_ns()

    sleep.__action__ = ActionMetadata(blocking=True)  # type: ignore
    rate.__action__ = ActionMetadata(blocking=True)  # type: ignore
    time_ns.__action__ = ActionMetadata(blocking=True)  # type: ignore
