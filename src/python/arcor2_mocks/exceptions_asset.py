from arcor2.flask import FlaskException, WebApiErrorFactory
from arcor2_mocks import __name__ as package_name


class AssetException(FlaskException):
    service = package_name


class Argument(AssetException):
    description = "Occurs when one of the arguments provided to a method is not valid."


class AssetSystem(AssetException):
    description = "Occurs when internal problem in asset system is encountered."


class AssetReference(AssetException):
    description = "Occurs when there is violation of references between assets."


class NotFound(AssetException):
    description = "Occurs when anything that was looked for is not found."


WebApiError = WebApiErrorFactory.get_class(Argument, AssetSystem, AssetReference)
