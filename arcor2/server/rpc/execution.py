from typing import Union
import tempfile
import os
import base64
import uuid


from arcor2.data import rpc
import arcor2.helpers as hlp
from arcor2 import rest

from arcor2.server.execution import manager_request
import arcor2.server.globals as glob


async def build_project_cb(req: rpc.execution.BuildProjectRequest) -> \
        Union[rpc.execution.BuildProjectResponse, hlp.RPC_RETURN_TYPES]:
    """
    Builds and executes the project.
    :param req:
    :return:
    """

    # call build service
    # TODO store data in memory
    with tempfile.TemporaryDirectory() as tmpdirname:

        path = os.path.join(tmpdirname, "publish.zip")

        try:
            await hlp.run_in_executor(rest.download, f"{glob.BUILDER_URL}/project/{req.args.id}/publish", path)
        except rest.RestException as e:
            await glob.logger.error(e)
            return False, str(e.message)

        with open(path, "rb") as zip_file:
            b64_bytes = base64.b64encode(zip_file.read())
            b64_str = b64_bytes.decode()

    # send data to execution service
    exe_req = rpc.execution.UploadPackageRequest(uuid.uuid4().int,
                                                 args=rpc.execution.UploadPackageArgs(req.args.id, b64_str))
    resp = await manager_request(exe_req)
    return resp.result, " ".join(resp.messages) if resp.messages else ""
