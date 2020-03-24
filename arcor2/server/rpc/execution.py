async def build_project_cb(req: rpc.execution.BuildProjectRequest) -> \
        Union[rpc.execution.BuildProjectResponse, hlp.RPC_RETURN_TYPES]:

    # call build service
    # TODO store data in memory
    with tempfile.TemporaryDirectory() as tmpdirname:

        path = os.path.join(tmpdirname, "publish.zip")

        try:
            await hlp.run_in_executor(rest.download, f"{BUILDER_URL}/project/{req.args.id}/publish", path)
        except rest.RestException as e:
            await logger.error(e)
            return False, "Failed to get project package."

        with open(path, "rb") as zip_file:
            b64_bytes = base64.b64encode(zip_file.read())
            b64_str = b64_bytes.decode()

    # send data to execution service
    exe_req = rpc.execution.UploadPackageRequest(uuid.uuid4().int,
                                                 args=rpc.execution.UploadPackageArgs(req.args.id, b64_str))
    resp = await manager_request(exe_req)
    return resp.result, " ".join(resp.messages) if resp.messages else ""