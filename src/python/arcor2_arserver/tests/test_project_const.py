import pytest

from arcor2 import json
from arcor2.data import common
from arcor2.object_types.random_actions import RandomActions
from arcor2_arserver.tests.testutils import event, lock_object, unlock_object
from arcor2_arserver_data import events, rpc
from arcor2_arserver_data.client import ARServer, get_id


@pytest.mark.additional_deps(["./src.python.arcor2.scripts/upload_builtin_objects.pex"])
def test_project_const(start_processes: None, ars: ARServer) -> None:

    event(ars, events.c.ShowMainScreen)

    assert ars.call_rpc(
        rpc.s.NewScene.Request(get_id(), rpc.s.NewScene.Request.Args("Test scene")), rpc.s.NewScene.Response
    ).result

    scene_data = event(ars, events.s.OpenScene).data
    assert scene_data
    scene = scene_data.scene

    event(ars, events.s.SceneState)

    assert ars.call_rpc(
        rpc.s.AddObjectToScene.Request(
            get_id(), rpc.s.AddObjectToScene.Request.Args("random_actions", RandomActions.__name__)
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
    open_project = event(ars, events.p.OpenProject).data
    assert open_project

    proj = open_project.project

    # test project parameters added by the arserver
    d: dict[str, common.ProjectParameter] = {par.name: par for par in proj.parameters}
    assert len(d) == 2
    assert d["scene_id"].type == "string"
    assert json.loads(d["scene_id"].value) == scene.id
    assert d["project_id"].type == "string"
    assert json.loads(d["project_id"].value) == proj.id

    event(ars, events.s.SceneState)

    assert ars.call_rpc(
        rpc.p.AddProjectParameter.Request(
            get_id(), rpc.p.AddProjectParameter.Request.Args("min_time", "double", json.dumps(0.45))
        ),
        rpc.p.AddProjectParameter.Response,
    ).result

    c1 = event(ars, events.p.ProjectParameterChanged).data
    assert c1

    assert not ars.call_rpc(
        rpc.p.AddProjectParameter.Request(
            get_id(), rpc.p.AddProjectParameter.Request.Args("min_time", "double", json.dumps(0.62))
        ),
        rpc.p.AddProjectParameter.Response,
    ).result

    assert not ars.call_rpc(  # attempt to update without lock
        rpc.p.UpdateProjectParameter.Request(
            get_id(), rpc.p.UpdateProjectParameter.Request.Args(c1.id, name="min_time_updated")
        ),
        rpc.p.UpdateProjectParameter.Response,
    ).result

    # ------------------------------------------------------------------------------------------------------------------
    # the user opens a menu and then closes it without actually changing anything

    lock_object(ars, c1.id)

    assert ars.call_rpc(
        rpc.p.UpdateProjectParameter.Request(
            get_id(), rpc.p.UpdateProjectParameter.Request.Args(c1.id, name="min_time_1"), dry_run=True
        ),
        rpc.p.UpdateProjectParameter.Response,
    ).result

    assert ars.call_rpc(
        rpc.p.UpdateProjectParameter.Request(
            get_id(), rpc.p.UpdateProjectParameter.Request.Args(c1.id, name="min_time_2"), dry_run=True
        ),
        rpc.p.UpdateProjectParameter.Response,
    ).result

    unlock_object(ars, c1.id)

    # ------------------------------------------------------------------------------------------------------------------

    lock_object(ars, c1.id)

    assert ars.call_rpc(
        rpc.p.UpdateProjectParameter.Request(
            get_id(), rpc.p.UpdateProjectParameter.Request.Args(c1.id, name="min_time_updated")
        ),
        rpc.p.UpdateProjectParameter.Response,
    ).result

    c1u = event(ars, events.p.ProjectParameterChanged).data
    assert c1u

    event(ars, events.lk.ObjectsUnlocked)

    assert c1u.id == c1.id
    assert c1.name != c1u.name
    assert c1.type == c1u.type

    # ------------------------------------------------------------------------------------------------------------------
    # try to add and remove

    assert ars.call_rpc(
        rpc.p.AddProjectParameter.Request(
            get_id(), rpc.p.AddProjectParameter.Request.Args("min_time_2", "double", json.dumps(0.62))
        ),
        rpc.p.AddProjectParameter.Response,
    ).result

    c2 = event(ars, events.p.ProjectParameterChanged).data
    assert c2

    # attempt to rename param to already used name
    assert not ars.call_rpc(
        rpc.p.UpdateProjectParameter.Request(get_id(), rpc.p.UpdateProjectParameter.Request.Args(c2.id, c1u.name)),
        rpc.p.AddProjectParameter.Response,
    ).result

    assert ars.call_rpc(
        rpc.p.RemoveProjectParameter.Request(get_id(), rpc.p.RemoveProjectParameter.Request.Args(c2.id)),
        rpc.p.RemoveProjectParameter.Response,
    ).result

    c2e = event(ars, events.p.ProjectParameterChanged)
    assert c2e.data
    assert c2e.data.id == c2.id
    assert c2e.change_type == c2e.Type.REMOVE

    # ------------------------------------------------------------------------------------------------------------------
    # attempt to add a constant with duplicate name

    assert not ars.call_rpc(
        rpc.p.AddProjectParameter.Request(
            get_id(), rpc.p.AddProjectParameter.Request.Args(c1u.name, "double", json.dumps(0.62))
        ),
        rpc.p.AddProjectParameter.Response,
    ).result

    # ------------------------------------------------------------------------------------------------------------------

    assert ars.call_rpc(
        rpc.p.AddActionPoint.Request(get_id(), rpc.p.AddActionPoint.Request.Args("ap1", common.Position())),
        rpc.p.AddActionPoint.Response,
    ).result

    ap = event(ars, events.p.ActionPointChanged).data
    assert ap is not None

    assert ars.call_rpc(
        rpc.p.AddAction.Request(
            get_id(),
            rpc.p.AddAction.Request.Args(
                ap.id,
                "test_action",
                f"{obj.id}/{RandomActions.random_double.__name__}",
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
    assert action

    assert not ars.call_rpc(
        rpc.p.RemoveProjectParameter.Request(get_id(), rpc.p.RemoveProjectParameter.Request.Args(c1.id)),
        rpc.p.RemoveProjectParameter.Response,
    ).result

    # ------------------------------------------------------------------------------------------------------------------
    # try to execute action using constant parameter

    assert ars.call_rpc((rpc.s.StartScene.Request(get_id())), rpc.s.StartScene.Response).result

    assert event(ars, events.s.SceneState).data.state == events.s.SceneState.Data.StateEnum.Starting
    assert event(ars, events.s.SceneState).data.state == events.s.SceneState.Data.StateEnum.Started

    assert ars.call_rpc(
        rpc.p.ExecuteAction.Request(get_id(), rpc.p.ExecuteAction.Request.Args(action.id)), rpc.p.ExecuteAction.Response
    )

    event(ars, events.a.ActionExecution)
    res = event(ars, events.a.ActionResult)

    assert res.data
    assert res.data.action_id == action.id
    assert not res.data.error

    assert ars.call_rpc((rpc.s.StopScene.Request(get_id())), rpc.s.StopScene.Response).result
    assert event(ars, events.s.SceneState).data.state == events.s.SceneState.Data.StateEnum.Stopping
    assert event(ars, events.s.SceneState).data.state == events.s.SceneState.Data.StateEnum.Stopped

    assert ars.call_rpc(
        rpc.p.RemoveAction.Request(get_id(), rpc.p.IdArgs(action.id)), rpc.p.RemoveAction.Response
    ).result
    assert event(ars, events.p.ActionChanged).data

    assert ars.call_rpc(
        rpc.p.RemoveProjectParameter.Request(get_id(), rpc.p.RemoveProjectParameter.Request.Args(c1.id)),
        rpc.p.RemoveProjectParameter.Response,
    ).result
    event(ars, events.p.ProjectParameterChanged)
