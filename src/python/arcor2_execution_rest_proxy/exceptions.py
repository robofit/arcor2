from arcor2.flask import FlaskException, WebApiErrorFactory
from arcor2_execution_rest_proxy import __name__ as package_name


class ExecutionRestProxyException(FlaskException):
    service = package_name


class RpcFail(ExecutionRestProxyException):
    description = "Occurs when underlying RPC fails."


class NotFound(ExecutionRestProxyException):
    description = "Occurs when something is missing."


class PackageRunState(ExecutionRestProxyException):
    description = "Occurs when package run state does not meet requirements."


WebApiError = WebApiErrorFactory.get_class(RpcFail, NotFound, PackageRunState)
