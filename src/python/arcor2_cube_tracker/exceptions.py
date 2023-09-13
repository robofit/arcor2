from arcor2.flask import FlaskException, General, WebApiErrorFactory
from arcor2_cube_tracker import __name__ as package_name


class CubeTrackerException(FlaskException):
    service = package_name


class CubeTrackerGeneral(CubeTrackerException):
    description = General.description


class NotFound(CubeTrackerException):
    description = "Occurs when something is not found."


WebApiError = WebApiErrorFactory.get_class(NotFound, CubeTrackerGeneral)
