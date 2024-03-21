import time

from arcor2.data.common import ActionMetadata
from arcor2.object_types.abstract import Generic


class Erp(Generic):
    """ObjectType that simulates Enterprise Resource Planning system."""

    _ABSTRACT = False

    def log_production_step(self, step: str, success: bool, *, an: None | str = None) -> None:
        """Logs finished production step.

        :param step: Name of the production step.
        :param success: Indicates whether the step was successful.
        :param an:
        :return:
        """

        time.sleep(0.01)

    log_production_step.__action__ = ActionMetadata()  # type: ignore
