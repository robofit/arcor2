import asyncio

from websockets.server import WebSocketServerProtocol as WsClient

from arcor2.data import rpc
from arcor2.exceptions import Arcor2Exception
from arcor2.server import decorators, globals as glob
from arcor2.server.execution import build_and_upload_package, run_temp_package


async def build_project_cb(req: rpc.execution.BuildProjectRequest, ui: WsClient) -> rpc.execution.BuildProjectResponse:
    """
    Builds project and uploads resulting package to the execution unit.
    :param req:
    :param ui:
    :return:
    """

    package_id = await build_and_upload_package(req.args.project_id, req.args.package_name)

    resp = rpc.execution.BuildProjectResponse()
    resp.data = rpc.execution.BuildProjectData(package_id)
    # TODO broadcast new package_id using event?
    return resp


@decorators.project_needed
async def temporary_package_cb(req: rpc.execution.TemporaryPackageRequest, ui: WsClient) -> None:

    assert glob.PROJECT

    if glob.PROJECT.has_changes:
        raise Arcor2Exception("Project has unsaved changes.")

    package_id = await build_and_upload_package(glob.PROJECT.id,
                                                f"Temporary package for project '{glob.PROJECT.name}'.")

    asyncio.ensure_future(run_temp_package(package_id))
    return None
