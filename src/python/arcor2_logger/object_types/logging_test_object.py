from arcor2.object_types.abstract import Generic, Settings

from .logging_mixin import LoggingMixin  # noqa:ABS101


class LoggingTestObject(LoggingMixin, Generic):
    _ABSTRACT = False

    def __init__(self, obj_id: str, name: str, settings: None | Settings = None) -> None:
        super().__init__(obj_id, name, settings)
        self.logger = self.get_logger()
        self.logger.info("Initialized.")

    def useless_action(self, *, an: None | str = None) -> None:
        self.logger.warning("Useless action called!")

    def cleanup(self) -> None:
        self.logger.info("Going to be cleaned up...")
        super().cleanup()
