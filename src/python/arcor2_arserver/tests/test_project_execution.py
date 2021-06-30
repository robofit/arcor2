import json

from arcor2.clients import project_service
from arcor2.data import common
from arcor2.data import events as arcor2_events
from arcor2.object_types.random_actions import RandomActions
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

    event(ars, events.s.SceneState)

    assert ars.call_rpc(
        rpc.s.AddObjectToScene.Request(
            uid(), rpc.s.AddObjectToScene.Request.Args("time_actions", TimeActions.__name__)
        ),
        rpc.s.AddObjectToScene.Response,
    ).result

    obj = event(ars, events.s.SceneObjectChanged).data
    assert obj

    assert ars.call_rpc(
        rpc.s.AddObjectToScene.Request(
            uid(), rpc.s.AddObjectToScene.Request.Args("random_actions", RandomActions.__name__)
        ),
        rpc.s.AddObjectToScene.Response,
    ).result

    obj2 = event(ars, events.s.SceneObjectChanged).data
    assert obj2

    # ------------------------------------------------------------------------------------------------------------------

    assert ars.call_rpc(
        rpc.p.NewProject.Request(uid(), rpc.p.NewProject.Request.Args(scene.id, "Project name")),
        rpc.p.NewProject.Response,
    ).result

    proj = event(ars, events.p.OpenProject).data
    assert proj

    event(ars, events.s.SceneState)

    assert ars.call_rpc(
        rpc.p.AddActionPoint.Request(uid(), rpc.p.AddActionPoint.Request.Args("ap1", common.Position())),
        rpc.p.AddActionPoint.Response,
    ).result

    ap = event(ars, events.p.ActionPointChanged).data
    assert ap is not None

    assert ars.call_rpc(
        rpc.p.AddProjectParameter.Request(
            uid(), rpc.p.AddProjectParameter.Request.Args("min_time", "double", json.dumps(0.45))
        ),
        rpc.p.AddActionPoint.Response,
    ).result

    c1 = event(ars, events.p.ProjectParameterChanged).data
    assert c1

    assert ars.call_rpc(
        rpc.p.AddAction.Request(
            uid(),
            rpc.p.AddAction.Request.Args(
                ap.id,
                "test_action",
                f"{obj2.id}/{RandomActions.random_double.__name__}",
                [
                    common.ActionParameter(
                        "range_min", common.ActionParameter.TypeEnum.PROJECT_PARAMETER, json.dumps(c1.id)
                    ),
                    common.ActionParameter("range_max", "double", "0.55"),
                ],
                [common.Flow(outputs=["random_value"])],
            ),
        ),
        rpc.p.AddAction.Response,
    ).result

    action = event(ars, events.p.ActionChanged).data
    assert action is not None

    assert ars.call_rpc(
        rpc.p.AddAction.Request(
            uid(),
            rpc.p.AddAction.Request.Args(
                ap.id,
                "test_action2",
                f"{obj.id}/{TimeActions.sleep.__name__}",
                [
                    common.ActionParameter(
                        "seconds",
                        common.ActionParameter.TypeEnum.LINK,
                        json.dumps(f"{action.id}/{common.FlowTypes.DEFAULT}/0"),
                    )
                ],
                [common.Flow()],
            ),
        ),
        rpc.p.AddAction.Response,
    ).result

    action2 = event(ars, events.p.ActionChanged).data
    assert action2 is not None

    add_logic_item(ars, common.LogicItem.START, action.id)
    event(ars, events.lk.ObjectsUnlocked)

    add_logic_item(ars, action.id, action2.id)
    event(ars, events.lk.ObjectsUnlocked)

    add_logic_item(ars, action2.id, common.LogicItem.END)
    event(ars, events.lk.ObjectsUnlocked)

    save_project(ars)

    LOGGER.debug(project_service.get_project(proj.project.id))

    # TODO test also temporary package

    close_project(ars)

    # ------------------------------------------------------------------------------------------------------------------

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

    # random_double action
    act_state_before = event(ars, arcor2_events.ActionStateBefore).data
    assert act_state_before
    assert act_state_before.action_id == action.id
    assert len(act_state_before.parameters) == 2

    act_state_after = event(ars, arcor2_events.ActionStateAfter).data
    assert act_state_after
    assert act_state_after.action_id == action.id
    assert act_state_after.results

    # sleep action
    act2_state_before = event(ars, arcor2_events.ActionStateBefore).data
    assert act2_state_before
    assert act2_state_before.action_id == action2.id
    assert len(act2_state_before.parameters) == 1

    act2_state_after = event(ars, arcor2_events.ActionStateAfter).data
    assert act2_state_after
    assert act2_state_after.action_id == action2.id
    assert not act2_state_after.results

    # TODO pause, resume

    assert ars.call_rpc(erpc.StopPackage.Request(uid()), erpc.StopPackage.Response).result

    ps2 = wait_for_event(ars, arcor2_events.PackageState).data
    assert ps2
    assert ps2.package_id == package.id
    assert ps2.state == ps.state.STOPPING

    ps3 = wait_for_event(ars, arcor2_events.PackageState).data
    assert ps3
    assert ps3.package_id == package.id
    assert ps3.state == ps.state.STOPPED

    show_main_screen_event = event(ars, events.c.ShowMainScreen)
    assert show_main_screen_event.data
    assert show_main_screen_event.data.what == events.c.ShowMainScreen.Data.WhatEnum.PackagesList
    assert show_main_screen_event.data.highlight == package.id
