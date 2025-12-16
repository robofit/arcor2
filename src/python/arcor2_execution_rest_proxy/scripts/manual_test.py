from arcor2_web import rest
from arcor2_execution_rest_proxy.scripts.execution_rest_proxy import ExecutionInfo, ExecutionState
import time
import requests

# TODO turn it into regular integration test

URL = "http://localhost:5009"
PKG = "ParTestPackage"

def wait_for(what: ExecutionState | set[ExecutionState], pkg_id: str | None = None, aps: set[str] | None = None) -> None:

    if isinstance(what, ExecutionState):
        what = {what}

    while True:

        # ...this can't be used because case proxy uses non-standard style/case (activePackageId)
        #ei = rest.call(rest.Method.GET, f"{URL}/packages/state", return_type=ExecutionInfo)
        ei = ExecutionInfo.from_dict(requests.get(f"{URL}/packages/state").json())

        if ei.state in what:
            print(ei)

            if pkg_id is not None:
                assert ei.activePackageId == pkg_id, (ei.activePackageId, pkg_id)

            if aps is not None:
                assert ei.actionPointIds is not None
                assert  aps.issubset(ei.actionPointIds), (ei.actionPointIds, aps)

            break
        else:
            print(f"Waiting for {what}, got {ei.state}")
        time.sleep(0.1)

if __name__ == "__main__":

    rest.call(rest.Method.PUT, f"{URL}/packages/{PKG}/start")
    try:
        rest.call(rest.Method.PUT, f"{URL}/packages/pause")
    except rest.WebApiError as e:
        print(f"Expected failure: {e}")
    wait_for(ExecutionState.Running, pkg_id=PKG)
    rest.call(rest.Method.PUT, f"{URL}/packages/pause")
    wait_for(ExecutionState.Paused, pkg_id=PKG)
    rest.call(rest.Method.PUT, f"{URL}/packages/stop")
    wait_for(ExecutionState.Completed)

    for breakpoint in ("r1_ap1", "r1_ap2", "r2_ap1"):

        rest.call(rest.Method.PUT, f"{URL}/packages/{PKG}/breakpoints", params={"breakpoints": [breakpoint]})
        rest.call(rest.Method.PUT, f"{URL}/packages/{PKG}/debug")
        wait_for(ExecutionState.Paused, pkg_id=PKG, aps={breakpoint})
        rest.call(rest.Method.PUT, f"{URL}/packages/stop")
        wait_for(ExecutionState.Completed)


