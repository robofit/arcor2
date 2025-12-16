from arcor2_dobot import __name__ as package_name
from arcor2_web.flask import FlaskException, General, WebApiErrorFactory


class DobotException(FlaskException):
    service = package_name


class DobotGeneral(DobotException):
    description = General.description


class NotFound(DobotException):
    description = "Occurs when something is not found"


class StartError(DobotException):
    description = "Occurs when start condition is not met"


WebApiError = WebApiErrorFactory.get_class(DobotGeneral, NotFound, StartError)
