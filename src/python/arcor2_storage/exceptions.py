from arcor2_storage import __name__ as package_name
from arcor2_web.flask import FlaskException, WebApiErrorFactory


class ProjectException(FlaskException):
    service = package_name


class ProjectGeneral(ProjectException):
    description = "Occurs when some requirements are not met."


class Argument(ProjectException):
    description = "Occurs when one of the arguments provided to a method is not valid."


class NotFound(ProjectException):
    description = "Occurs when something is not found."


WebApiError = WebApiErrorFactory.get_class(ProjectGeneral, NotFound, Argument)
