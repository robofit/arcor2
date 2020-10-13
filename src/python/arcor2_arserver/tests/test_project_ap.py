import pytest  # type: ignore

from arcor2.data import common
from arcor2_arserver.tests.conftest import event
from arcor2_arserver_data import events, rpc
from arcor2_arserver_data.client import ARServer, uid


@pytest.mark.skip(reason="Not finished yet.")
def test_project_ap_rpcs(start_processes: None, ars: ARServer, scene: common.Scene) -> None:

    assert ars.call_rpc(
        rpc.p.NewProject.Request(uid(), rpc.p.NewProject.Request.Args(scene.id, "Project name")),
        rpc.p.NewProject.Response,
    ).result

    event(ars, events.p.OpenProject)

    # TODO add object-AP, global AP, etc.
