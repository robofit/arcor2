from arcor2.flask import FlaskException, WebApiErrorFactory
from arcor2_mocks import __name__ as package_name


class ProjectException(FlaskException):
    service = package_name


class ProjectGeneral(ProjectException):
    description = "Occurs when some requirements are not met."


class NotFound(ProjectException):
    description = "Occurs when something is not found."


WebApiError = WebApiErrorFactory.get_class(ProjectGeneral, NotFound)
