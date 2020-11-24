import logging

import aiologger

LOG_FORMAT = "%(asctime)s - %(levelname)-8s: %(message)s", "%Y-%m-%d %H:%M:%S"


def aiologger_formatter() -> aiologger.formatters.base.Formatter:

    return aiologger.formatters.base.Formatter(*LOG_FORMAT)


def logger_formatter() -> logging.Formatter:

    return logging.Formatter(*LOG_FORMAT)


def get_aiologger(name: str, level: aiologger.levels.LogLevel = aiologger.levels.LogLevel.INFO) -> aiologger.Logger:

    return aiologger.Logger.with_default_handlers(name=name, formatter=aiologger_formatter(), level=level)


def get_logger(name: str, level: int = logging.INFO) -> logging.Logger:

    logger = logging.getLogger(name)

    ch = logging.StreamHandler()
    ch.setFormatter(logger_formatter())
    logger.setLevel(level)
    logger.addHandler(ch)

    return logger
