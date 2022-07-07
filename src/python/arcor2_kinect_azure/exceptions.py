from arcor2.flask import FlaskException, WebApiErrorFactory
from arcor2_kinect_azure import __name__ as package_name


class KinectAzureException(FlaskException):
    service = package_name


class NotFound(KinectAzureException):
    description = "Occurs when something is not found."


class StartError(KinectAzureException):
    description = "Occurs when start condition is not met."


WebApiError = WebApiErrorFactory.get_class(StartError, NotFound)
