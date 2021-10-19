import asyncio

from websockets.server import WebSocketServerProtocol as WsClient

from arcor2.exceptions import Arcor2Exception
from arcor2_arserver import globals as glob
from arcor2_arserver.execution import build_and_upload_package, run_temp_package
from arcor2_arserver.helpers import ctx_write_lock
from arcor2_arserver_data import rpc


async def build_project_cb(req: rpc.b.BuildProject.Request, ui: WsClient) -> rpc.b.BuildProject.Response:
    """Builds project and uploads resulting package to the execution unit.

    :param req:
    :param ui:
    :return:
    """

    async with ctx_write_lock(req.args.project_id, glob.USERS.user_name(ui)):
        package_id = await build_and_upload_package(req.args.project_id, req.args.package_name)

        resp = rpc.b.BuildProject.Response()
        resp.data = resp.Data(package_id)
        return resp


async def temporary_package_cb(req: rpc.b.TemporaryPackage.Request, ui: WsClient) -> None:

    async with glob.LOCK.get_lock():

        project = glob.LOCK.project_or_exception()

        if project.has_changes:
            raise Arcor2Exception("Project has unsaved changes.")

        package_id = await build_and_upload_package(project.id, f"Temporary package for project '{project.name}'.")

        if req.args:
            paused = req.args.start_paused
            breakpoints = req.args.breakpoints
        else:
            paused = False
            breakpoints = None

        asyncio.ensure_future(run_temp_package(package_id, paused, breakpoints))
        return None
