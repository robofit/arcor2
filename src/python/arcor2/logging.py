import logging

import aiologger
import colorlog


def getMessage(self):
    """backwards compatibility for python builtin logger ref.

    python3.7/logging/__init__.py", line 608
    """
    return self.get_message()


# see https://github.com/b2wdigital/aiologger/pull/85
aiologger.records.LogRecord.getMessage = getMessage


DEFAULT_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
DEFAULT_LOG_FORMAT = "%(asctime)s %(log_color)s%(levelname)-8s%(reset)s %(message)s"


def logger_formatter(log_format=DEFAULT_LOG_FORMAT, date_format=DEFAULT_DATE_FORMAT) -> logging.Formatter:

    return colorlog.ColoredFormatter(log_format, date_format)


def get_aiologger(
    name: str,
    level: aiologger.levels.LogLevel = aiologger.levels.LogLevel.INFO,
    formatter: None | logging.Formatter = None,
) -> aiologger.Logger:

    if formatter is None:
        formatter = logger_formatter()

    return aiologger.Logger.with_default_handlers(name=name, formatter=formatter, level=level)


def get_logger(name: str, level: int = logging.INFO) -> logging.Logger:

    logger = logging.getLogger(name)

    ch = logging.StreamHandler()
    ch.setFormatter(logger_formatter())
    logger.setLevel(level)
    logger.addHandler(ch)

    return logger
