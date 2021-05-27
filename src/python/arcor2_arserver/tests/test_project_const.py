from arcor2 import json
from arcor2.data import common
from arcor2.object_types.random_actions import RandomActions
from arcor2_arserver.tests.conftest import event, lock_object, unlock_object
from arcor2_arserver_data import events, rpc
from arcor2_arserver_data.client import ARServer, uid


def test_project_const(start_processes: None, ars: ARServer) -> None:

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
            uid(), rpc.s.AddObjectToScene.Request.Args("random_actions", RandomActions.__name__)
        ),
        rpc.s.AddObjectToScene.Response,
    ).result

    obj = event(ars, events.s.SceneObjectChanged).data
    assert obj

    # ------------------------------------------------------------------------------------------------------------------

    assert ars.call_rpc(
        rpc.p.NewProject.Request(uid(), rpc.p.NewProject.Request.Args(scene.id, "Project name")),
        rpc.p.NewProject.Response,
    ).result

    proj = event(ars, events.p.OpenProject).data
    assert proj

    event(ars, events.s.SceneState)

    assert ars.call_rpc(
        rpc.p.AddConstant.Request(uid(), rpc.p.AddConstant.Request.Args("min_time", "double", json.dumps(0.45))),
        rpc.p.AddConstant.Response,
    ).result

    c1 = event(ars, events.p.ProjectConstantChanged).data
    assert c1

    assert not ars.call_rpc(
        rpc.p.AddConstant.Request(uid(), rpc.p.AddConstant.Request.Args("min_time", "double", json.dumps(0.62))),
        rpc.p.AddConstant.Response,
    ).result

    assert not ars.call_rpc(  # attempt to update without lock
        rpc.p.UpdateConstant.Request(uid(), rpc.p.UpdateConstant.Request.Args(c1.id, name="min_time_updated")),
        rpc.p.UpdateConstant.Response,
    ).result

    # ------------------------------------------------------------------------------------------------------------------
    # the user opens a menu and then closes it without actually changing anything

    lock_object(ars, c1.id)

    assert ars.call_rpc(
        rpc.p.UpdateConstant.Request(uid(), rpc.p.UpdateConstant.Request.Args(c1.id, name="min_time_1"), dry_run=True),
        rpc.p.UpdateConstant.Response,
    ).result

    assert ars.call_rpc(
        rpc.p.UpdateConstant.Request(uid(), rpc.p.UpdateConstant.Request.Args(c1.id, name="min_time_2"), dry_run=True),
        rpc.p.UpdateConstant.Response,
    ).result

    unlock_object(ars, c1.id)

    # ------------------------------------------------------------------------------------------------------------------

    lock_object(ars, c1.id)

    assert ars.call_rpc(
        rpc.p.UpdateConstant.Request(uid(), rpc.p.UpdateConstant.Request.Args(c1.id, name="min_time_updated")),
        rpc.p.UpdateConstant.Response,
    ).result

    c1u = event(ars, events.p.ProjectConstantChanged).data
    assert c1u

    event(ars, events.lk.ObjectsUnlocked)

    assert c1u.id == c1.id
    assert c1.name != c1u.name
    assert c1.type == c1u.type

    # ------------------------------------------------------------------------------------------------------------------
    # try to add and remove

    assert ars.call_rpc(
        rpc.p.AddConstant.Request(uid(), rpc.p.AddConstant.Request.Args("min_time_2", "double", json.dumps(0.62))),
        rpc.p.AddConstant.Response,
    ).result

    c2 = event(ars, events.p.ProjectConstantChanged).data
    assert c2

    assert ars.call_rpc(
        rpc.p.RemoveConstant.Request(uid(), rpc.p.RemoveConstant.Request.Args(c2.id)),
        rpc.p.RemoveConstant.Response,
    ).result

    c2e = event(ars, events.p.ProjectConstantChanged)
    assert c2e.data
    assert c2e.data.id == c2.id
    assert c2e.change_type == c2e.Type.REMOVE

    # ------------------------------------------------------------------------------------------------------------------
    # attempt to add a constant with duplicate name

    assert not ars.call_rpc(
        rpc.p.AddConstant.Request(uid(), rpc.p.AddConstant.Request.Args(c1u.name, "double", json.dumps(0.62))),
        rpc.p.AddConstant.Response,
    ).result

    # ------------------------------------------------------------------------------------------------------------------

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
                f"{obj.id}/{RandomActions.random_double.__name__}",
                [
                    common.ActionParameter("range_min", common.ActionParameter.TypeEnum.CONSTANT, json.dumps(c1.id)),
                    common.ActionParameter("range_max", "double", "0.55"),
                ],
                [common.Flow(outputs=["random_value"])],
            ),
        ),
        rpc.p.AddAction.Response,
    ).result

    action = event(ars, events.p.ActionChanged).data
    assert action

    assert not ars.call_rpc(
        rpc.p.RemoveConstant.Request(uid(), rpc.p.RemoveConstant.Request.Args(c1.id)), rpc.p.RemoveConstant.Response
    ).result

    # ------------------------------------------------------------------------------------------------------------------
    # try to execute action using constant parameter

    assert ars.call_rpc((rpc.s.StartScene.Request(uid())), rpc.s.StartScene.Response).result

    event(ars, events.s.SceneState)
    event(ars, events.s.SceneState)

    assert ars.call_rpc(
        rpc.p.ExecuteAction.Request(uid(), rpc.p.ExecuteAction.Request.Args(action.id)), rpc.p.ExecuteAction.Response
    )

    event(ars, events.a.ActionExecution)
    res = event(ars, events.a.ActionResult)

    assert res.data
    assert res.data.action_id == action.id
    assert not res.data.error

    assert ars.call_rpc((rpc.s.StopScene.Request(uid())), rpc.s.StopScene.Response).result
    event(ars, events.s.SceneState)
    event(ars, events.s.SceneState)

    assert ars.call_rpc(rpc.p.RemoveAction.Request(uid(), rpc.p.IdArgs(action.id)), rpc.p.RemoveAction.Response).result
    assert event(ars, events.p.ActionChanged).data

    assert ars.call_rpc(
        rpc.p.RemoveConstant.Request(uid(), rpc.p.RemoveConstant.Request.Args(c1.id)), rpc.p.RemoveConstant.Response
    ).result
    event(ars, events.p.ProjectConstantChanged)
