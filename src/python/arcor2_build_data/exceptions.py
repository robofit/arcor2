from arcor2.flask import FlaskException, WebApiErrorFactory


class BuildServiceException(FlaskException):
    """Base flask exception for build service."""

    service = "arcor2_build"


class NotFound(BuildServiceException):
    description = "Occurs when something is missing."


class InvalidPackage(BuildServiceException):
    description = "Occurs when execution package is invalid."


class Conflict(BuildServiceException):
    description = "Occurs when a difference between package or project service detected."


class InvalidProject(BuildServiceException):
    description = "Occurs when project is invalid."


WebApiError = WebApiErrorFactory.get_class(NotFound, InvalidPackage, Conflict, InvalidProject)
