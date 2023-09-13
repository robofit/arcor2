from arcor2.flask import FlaskException, WebApiErrorFactory
from arcor2_cube_detector import __name__ as package_name


class CubeDetectorException(FlaskException):
    service = package_name


class DetectorNotStarted(CubeDetectorException):
    description = "Detector is not started."


WebApiError = WebApiErrorFactory.get_class(DetectorNotStarted)
