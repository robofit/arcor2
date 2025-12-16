from arcor2_logger.object_types.logging_mixin import LoggingMixin
from arcor2_logger.object_types.logging_test_object import LoggingTestObject
from arcor2_logger.object_types.logging_test_robot import LoggingTestRobot
from arcor2_object_types.upload import upload_def, upload_whatever


def main() -> None:
    upload_def(LoggingTestObject)
    upload_def(LoggingTestRobot)
    upload_whatever(LoggingMixin)


if __name__ == "__main__":
    main()
