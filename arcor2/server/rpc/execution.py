from typing import Union
import tempfile
import os
import base64
import uuid


from arcor2.data import rpc
import arcor2.helpers as hlp
from arcor2 import rest
from arcor2.data import common

from arcor2.server.execution import manager_request
import arcor2.server.globals as glob


async def build_project_cb(req: rpc.execution.BuildProjectRequest) -> \
        Union[rpc.execution.BuildProjectResponse, hlp.RPC_RETURN_TYPES]:
    """
    Builds project and uploads resulting package to the execution unit.
    :param req:
    :return:
    """

    package_id = common.uid()

    # call build service
    # TODO store data in memory
    with tempfile.TemporaryDirectory() as tmpdirname:

        path = os.path.join(tmpdirname, "publish.zip")

        await hlp.run_in_executor(rest.download, f"{glob.BUILDER_URL}/project/{req.args.project_id}/publish", path)

        with open(path, "rb") as zip_file:
            b64_bytes = base64.b64encode(zip_file.read())
            b64_str = b64_bytes.decode()

    # send data to execution service
    # TODO package_name (instead of ID)
    exe_req = rpc.execution.UploadPackageRequest(uuid.uuid4().int,
                                                 args=rpc.execution.UploadPackageArgs(package_id, b64_str))
    exe_resp = await manager_request(exe_req)

    resp = rpc.execution.BuildProjectResponse()
    resp.data = rpc.execution.BuildProjectData(package_id)
    resp.result = exe_resp.result
    resp.messages = exe_resp.messages

    return resp
