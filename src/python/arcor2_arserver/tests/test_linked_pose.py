import json

from arcor2.data import common
from arcor2.data import events as arcor2_events
from arcor2.data.common import ActionParameter, Flow, Pose, Position
from arcor2_arserver.tests.objects.object_returning_pose import ObjectReturningPose
from arcor2_arserver.tests.testutils import (
    add_logic_item,
    close_project,
    event,
    lock_object,
    save_project,
    unlock_object,
    wait_for_event,
)
from arcor2_arserver_data import events, rpc
from arcor2_arserver_data.client import ARServer, get_id
from arcor2_execution_data import events as eevents
from arcor2_execution_data import rpc as erpc
from arcor2_object_types.upload import upload_def


def test_linked_pose(start_processes: None, ars: ARServer) -> None:
    upload_def(ObjectReturningPose)

    event(ars, events.c.ShowMainScreen)

    assert ars.call_rpc(
        rpc.s.NewScene.Request(get_id(), rpc.s.NewScene.Request.Args("Test scene")), rpc.s.NewScene.Response
    ).result

    assert len(event(ars, events.o.ChangedObjectTypes).data) == 1

    scene_data = event(ars, events.s.OpenScene).data
    assert scene_data
    scene = scene_data.scene

    event(ars, events.s.SceneState)

    assert ars.call_rpc(
        rpc.s.AddObjectToScene.Request(
            get_id(), rpc.s.AddObjectToScene.Request.Args("pp", ObjectReturningPose.__name__)
        ),
        rpc.s.AddObjectToScene.Response,
    ).result

    obj = event(ars, events.s.SceneObjectChanged).data
    assert obj

    # ------------------------------------------------------------------------------------------------------------------

    assert ars.call_rpc(
        rpc.p.NewProject.Request(get_id(), rpc.p.NewProject.Request.Args(scene.id, "Project name")),
        rpc.p.NewProject.Response,
    ).result

    event(ars, events.s.SceneSaved)
    project_evt = event(ars, events.p.OpenProject)
    event(ars, events.s.SceneState)

    assert ars.call_rpc(
        rpc.p.AddActionPoint.Request(get_id(), rpc.p.AddActionPoint.Request.Args("parent_ap", Position())),
        rpc.p.AddActionPoint.Response,
    ).result

    ap_evt = event(ars, events.p.ActionPointChanged)

    lock_object(ars, ap_evt.data.id)

    assert ars.call_rpc(
        rpc.p.AddAction.Request(
            get_id(),
            rpc.p.AddAction.Request.Args(
                ap_evt.data.id,
                "a1",
                f"{obj.id}/{ObjectReturningPose.action_returning_pose.__name__}",
                [],
                [Flow(outputs=["pose"])],
            ),
        ),
        rpc.p.AddAction.Response,
    ).result

    a1_evt = event(ars, events.p.ActionChanged)

    # link: action_id, flow_name, output_idx_str

    assert ars.call_rpc(
        rpc.p.AddAction.Request(
            get_id(),
            rpc.p.AddAction.Request.Args(
                ap_evt.data.id,
                "a2",
                f"{obj.id}/{ObjectReturningPose.action_taking_pose.__name__}",
                [
                    ActionParameter(
                        "param", ActionParameter.TypeEnum.LINK, json.dumps(f"{a1_evt.data.id}/{Flow.type.DEFAULT}/0")
                    )
                ],
                [Flow()],
            ),
        ),
        rpc.p.AddAction.Response,
    ).result

    a2_evt = event(ars, events.p.ActionChanged)

    unlock_object(ars, ap_evt.data.id)

    # ------------------------------------------------------------------------------------------------------------------
    # try to execute action within ARServer

    assert ars.call_rpc((rpc.s.StartScene.Request(get_id())), rpc.s.StartScene.Response).result

    assert event(ars, events.s.SceneState).data.state == events.s.SceneState.Data.StateEnum.Starting
    assert event(ars, events.s.SceneState).data.state == events.s.SceneState.Data.StateEnum.Started

    assert ars.call_rpc(
        rpc.p.ExecuteAction.Request(get_id(), rpc.p.ExecuteAction.Request.Args(a1_evt.data.id)),
        rpc.p.ExecuteAction.Response,
    )

    event(ars, events.a.ActionExecution)
    res = event(ars, events.a.ActionResult)

    assert res.data
    assert res.data.action_id == a1_evt.data.id
    assert not res.data.error
    assert res.data.results
    assert len(res.data.results) == 1
    Pose.from_json(res.data.results[0])

    assert ars.call_rpc(
        rpc.p.ExecuteAction.Request(get_id(), rpc.p.ExecuteAction.Request.Args(a2_evt.data.id)),
        rpc.p.ExecuteAction.Response,
    )

    event(ars, events.a.ActionExecution)
    res = event(ars, events.a.ActionResult)

    assert res.data
    assert res.data.action_id == a2_evt.data.id
    assert not res.data.error

    assert ars.call_rpc((rpc.s.StopScene.Request(get_id())), rpc.s.StopScene.Response).result
    assert event(ars, events.s.SceneState).data.state == events.s.SceneState.Data.StateEnum.Stopping
    assert event(ars, events.s.SceneState).data.state == events.s.SceneState.Data.StateEnum.Stopped

    # ------------------------------------------------------------------------------------------------------------------

    add_logic_item(ars, common.LogicItem.START, a1_evt.data.id)
    event(ars, events.lk.ObjectsUnlocked)

    add_logic_item(ars, a1_evt.data.id, a2_evt.data.id)
    event(ars, events.lk.ObjectsUnlocked)

    add_logic_item(ars, a2_evt.data.id, common.LogicItem.END)
    event(ars, events.lk.ObjectsUnlocked)

    save_project(ars)
    # TODO test also temporary package
    close_project(ars)

    # ------------------------------------------------------------------------------------------------------------------
    # try building and running

    event(ars, events.c.ShowMainScreen)

    assert ars.call_rpc(
        rpc.b.BuildProject.Request(
            get_id(), rpc.b.BuildProject.Request.Args(project_evt.data.project.id, "Package name")
        ),
        rpc.b.BuildProject.Response,
    ).result

    package = event(ars, eevents.PackageChanged).data
    assert package is not None

    assert ars.call_rpc(
        erpc.RunPackage.Request(get_id(), erpc.RunPackage.Request.Args(package.id)), erpc.RunPackage.Response
    ).result

    ps = event(ars, arcor2_events.PackageState).data
    assert ps
    assert ps.package_id == package.id
    assert ps.state == ps.state.STARTED

    pr = event(ars, arcor2_events.PackageState).data
    assert pr
    assert pr.package_id == package.id
    assert pr.state == ps.state.RUNNING

    pi = event(ars, arcor2_events.PackageInfo).data
    assert pi
    assert pi.package_id == package.id

    act_state_before = event(ars, arcor2_events.ActionStateBefore).data
    assert act_state_before
    assert act_state_before.action_id == a1_evt.data.id
    assert not act_state_before.parameters
    act_state_after = event(ars, arcor2_events.ActionStateAfter).data
    assert act_state_after
    assert act_state_after.action_id == a1_evt.data.id

    act_state_before = event(ars, arcor2_events.ActionStateBefore).data
    assert act_state_before
    assert act_state_before.action_id == a2_evt.data.id
    assert act_state_before.parameters
    assert len(act_state_before.parameters) == 1
    act_state_after = event(ars, arcor2_events.ActionStateAfter).data
    assert act_state_after
    assert act_state_after.action_id == a2_evt.data.id

    assert ars.call_rpc(erpc.StopPackage.Request(get_id()), erpc.StopPackage.Response).result

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
