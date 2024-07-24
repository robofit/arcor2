from arcor2.flask import FlaskException, General, WebApiErrorFactory
from arcor2_ur import __name__ as package_name


class UrException(FlaskException):
    service = package_name


class UrGeneral(UrException):
    description = General.description


class NotFound(UrException):
    description = "Occurs when something is not found"


class StartError(UrException):
    description = "Occurs when start condition is not met"


WebApiError = WebApiErrorFactory.get_class(UrGeneral, NotFound, StartError)
