from arcor2.flask import FlaskException, WebApiErrorFactory


class CalibrationServiceException(FlaskException):
    """Base flask exception for calibration service."""

    service = "arcor2_calibration"


class NotFound(CalibrationServiceException):
    description = "Occurs when something is missing."


class Invalid(CalibrationServiceException):
    description = "Occurs when input is invalid."


WebApiError = WebApiErrorFactory.get_class(NotFound, Invalid)
