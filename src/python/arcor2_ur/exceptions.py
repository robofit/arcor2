from arcor2_ur import __name__ as package_name
from arcor2_web.flask import FlaskException, General, WebApiErrorFactory


class UrException(FlaskException):
    service = package_name


class UrGeneral(UrException):
    description = General.description


class UrCollisions(UrException):
    description = "Something regarding collision objects went wrong"


class NotFound(UrException):
    description = "Occurs when something is not found"


class StartError(UrException):
    description = "Occurs when start condition is not met"


WebApiError = WebApiErrorFactory.get_class(UrGeneral, NotFound, StartError)
