import logging
from functools import wraps
from typing import Callable, ParamSpec, TypeVar

from flask import request

from arcor2_kinect_azure import app
from arcor2_kinect_azure.exceptions import StartError


def started() -> bool:
    if app.MOCK:
        return app.MOCK_STARTED

    return app.KINECT is not None


P = ParamSpec("P")
R = TypeVar("R")
F = Callable[P, R]


def requires_started(f: F) -> Callable[P, R]:
    @wraps(f)
    def wrapped(*args: P.args, **kwargs: P.kwargs):
        if not started():
            raise StartError("Not started")
        return f(*args, **kwargs)

    return wrapped


def debug_request() -> None:
    flask_logger = logging.getLogger("werkzeug")

    flask_logger.debug(f"Request query params: {request.args}")
    flask_logger.debug(f"Request raw data: {request.data!r}")


__all__ = [requires_started.__name__, started.__name__]
