from arcor2.clients import persistent_storage
from arcor2.data import common
from arcor2.data import events as arcor2_events
from arcor2.object_types.time_actions import TimeActions
from arcor2_arserver.tests.conftest import LOGGER, add_logic_item, close_project, event, save_project, wait_for_event
from arcor2_arserver_data import events, rpc
from arcor2_arserver_data.client import ARServer, uid
from arcor2_execution_data import events as eevents
from arcor2_execution_data import rpc as erpc


def test_run_simple_project(start_processes: None, ars: ARServer) -> None:

    event(ars, events.c.ShowMainScreen)

    assert ars.call_rpc(
        rpc.s.NewScene.Request(uid(), rpc.s.NewScene.Request.Args("Test scene")), rpc.s.NewScene.Response
    ).result

    scene_data = event(ars, events.s.OpenScene).data
    assert scene_data
    scene = scene_data.scene

    assert ars.call_rpc(
        rpc.s.AddObjectToScene.Request(
            uid(), rpc.s.AddObjectToScene.Request.Args("time_actions", TimeActions.__name__)
        ),
        rpc.s.AddObjectToScene.Response,
    ).result

    obj = event(ars, events.s.SceneObjectChanged).data
    assert obj

    assert ars.call_rpc(
        rpc.p.NewProject.Request(uid(), rpc.p.NewProject.Request.Args(scene.id, "Project name")),
        rpc.p.NewProject.Response,
    ).result

    proj = event(ars, events.p.OpenProject).data
    assert proj

    assert ars.call_rpc(
        rpc.p.AddActionPoint.Request(uid(), rpc.p.AddActionPoint.Request.Args("ap1", common.Position())),
        rpc.p.AddActionPoint.Response,
    ).result

    ap = event(ars, events.p.ActionPointChanged).data
    assert ap is not None

    assert ars.call_rpc(
        rpc.p.AddAction.Request(
            uid(),
            rpc.p.AddAction.Request.Args(
                ap.id,
                "test_action",
                f"{obj.id}/{TimeActions.sleep.__name__}",
                [common.ActionParameter("seconds", "double", "0.5")],
                [common.Flow()],
            ),
        ),
        rpc.p.AddAction.Response,
    ).result

    action = event(ars, events.p.ActionChanged).data
    assert action is not None

    add_logic_item(ars, common.LogicItem.START, action.id)
    add_logic_item(ars, action.id, common.LogicItem.END)

    save_project(ars)

    LOGGER.debug(persistent_storage.get_project(proj.project.id))

    # TODO test also temporary package

    close_project(ars)

    event(ars, events.c.ShowMainScreen)

    assert ars.call_rpc(
        rpc.b.BuildProject.Request(uid(), rpc.b.BuildProject.Request.Args(proj.project.id, "Package name")),
        rpc.b.BuildProject.Response,
    ).result

    package = event(ars, eevents.PackageChanged).data
    assert package is not None

    assert ars.call_rpc(
        erpc.RunPackage.Request(uid(), erpc.RunPackage.Request.Args(package.id)), erpc.RunPackage.Response
    ).result

    ps = event(ars, arcor2_events.PackageState).data
    assert ps
    assert ps.package_id == package.id
    assert ps.state == ps.state.RUNNING

    pi = event(ars, arcor2_events.PackageInfo).data
    assert pi
    assert pi.package_id == package.id

    act_state_before = event(ars, arcor2_events.ActionStateBefore).data
    assert act_state_before
    assert act_state_before.action_id == action.id
    assert len(act_state_before.parameters) == 1
    # assert act_in.args[0].name == "seconds"
    # assert act_in.args[0].type == "double"
    # assert act_in.args[0].value == "0.1"

    act_state_after = event(ars, arcor2_events.ActionStateAfter).data
    assert act_state_after
    assert act_state_after.action_id == action.id
    assert not act_state_after.results

    # TODO pause, resume

    assert ars.call_rpc(erpc.StopPackage.Request(uid()), erpc.StopPackage.Response).result

    ps2 = wait_for_event(ars, arcor2_events.PackageState).data
    assert ps2
    assert ps2.package_id == package.id
    assert ps2.state == ps.state.STOPPED

    show_main_screen_event = event(ars, events.c.ShowMainScreen)
    assert show_main_screen_event.data
    assert show_main_screen_event.data.what == events.c.ShowMainScreen.Data.WhatEnum.PackagesList
    assert show_main_screen_event.data.highlight == package.id
