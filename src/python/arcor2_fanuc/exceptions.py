from arcor2.flask import FlaskException, General, WebApiErrorFactory
from arcor2_fanuc import __name__ as package_name


class FanucException(FlaskException):
    service = package_name


class FanucGeneral(FanucException):
    description = General.description


class NotFound(FanucException):
    description = "Occurs when something is not found."


class StartError(FanucException):
    description = "Occurs when start condition is not met."


WebApiError = WebApiErrorFactory.get_class(FanucGeneral, StartError, NotFound)
