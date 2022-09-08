from arcor2.flask import FlaskException, WebApiErrorFactory
from arcor2_scene import __name__ as package_name


class SceneException(FlaskException):
    service = package_name


class SceneGeneral(SceneException):
    description = "Occurs when some requirements are not met."


class NotFound(SceneException):
    description = "Occurs when something is not found."


WebApiError = WebApiErrorFactory.get_class(SceneGeneral, NotFound)
