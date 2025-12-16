import time

from arcor2.data.common import ActionMetadata
from arcor2_object_types.abstract import Generic


class TimeActions(Generic):
    """Provides time-related actions."""

    _ABSTRACT = False

    def sleep(self, seconds: float, *, an: None | str = None) -> None:
        """Sleeps for a given number of seconds."""

        time.sleep(seconds)

    sleep.__action__ = ActionMetadata()  # type: ignore
