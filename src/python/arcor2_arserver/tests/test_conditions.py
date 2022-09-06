import json

from arcor2.data.common import Flow, FlowTypes, LogicItem, Position, ProjectLogicIf, Scene
from arcor2.data.rpc import get_id
from arcor2.data.rpc.common import IdArgs
from arcor2.object_types.upload import upload_def
from arcor2_arserver.tests.objects.object_with_actions import ObjectWithActions
from arcor2_arserver.tests.testutils import add_logic_item, event, lock_object, save_project
from arcor2_arserver_data import events, rpc
from arcor2_arserver_data.client import ARServer


def test_object_parameters(start_processes: None, ars: ARServer, scene: Scene) -> None:

    upload_def(ObjectWithActions)

    assert ars.call_rpc(rpc.s.OpenScene.Request(get_id(), IdArgs(scene.id)), rpc.s.OpenScene.Response).result

    assert len(event(ars, events.o.ChangedObjectTypes).data) == 1

    event(ars, events.s.OpenScene)
    event(ars, events.s.SceneState)

    assert ars.call_rpc(
        rpc.s.AddObjectToScene.Request(
            get_id(), rpc.s.AddObjectToScene.Request.Args("ows", ObjectWithActions.__name__)
        ),
        rpc.s.AddObjectToScene.Response,
    ).result

    obj = event(ars, events.s.SceneObjectChanged).data
    assert obj is not None

    assert ars.call_rpc(
        rpc.p.NewProject.Request(get_id(), rpc.p.NewProject.Request.Args(scene.id, "Project name")),
        rpc.p.NewProject.Response,
    ).result

    event(ars, events.s.SceneSaved)
    event(ars, events.p.OpenProject)
    event(ars, events.s.SceneState)

    assert ars.call_rpc(
        rpc.p.AddActionPoint.Request(get_id(), rpc.p.AddActionPoint.Request.Args("ap", Position())),
        rpc.p.AddActionPoint.Response,
    ).result

    ap = event(ars, events.p.ActionPointChanged).data
    assert ap is not None

    assert ars.call_rpc(
        rpc.p.AddAction.Request(
            get_id(),
            rpc.p.AddAction.Request.Args(
                ap.id,
                "a1",
                f"{obj.id}/{ObjectWithActions.bool_action.__name__}",
                [],
                [Flow(outputs=["bool_result"])],
            ),
        ),
        rpc.p.AddAction.Response,
    ).result

    a1 = event(ars, events.p.ActionChanged).data
    assert a1 is not None

    assert ars.call_rpc(
        rpc.p.AddAction.Request(
            get_id(),
            rpc.p.AddAction.Request.Args(
                ap.id,
                "a2",
                f"{obj.id}/{ObjectWithActions.str_action.__name__}",
                [],
                [Flow()],
            ),
        ),
        rpc.p.AddAction.Response,
    ).result

    a2 = event(ars, events.p.ActionChanged).data
    assert a2 is not None

    add_logic_item(ars, LogicItem.START, a1.id)
    event(ars, events.lk.ObjectsUnlocked)

    lock_object(ars, a1.id)
    add_logic_item(ars, a1.id, a2.id, ProjectLogicIf(f"{a1.id}/{FlowTypes.DEFAULT}/{0}", json.dumps(True)))
    event(ars, events.lk.ObjectsUnlocked)

    lock_object(ars, a2.id)
    add_logic_item(ars, a2.id, LogicItem.END)
    event(ars, events.lk.ObjectsUnlocked)

    lock_object(ars, a1.id)
    add_logic_item(ars, a1.id, LogicItem.END, ProjectLogicIf(f"{a1.id}/{FlowTypes.DEFAULT}/{0}", json.dumps(False)))
    event(ars, events.lk.ObjectsUnlocked)

    # TODO try to add some invalid connections here?

    save_project(ars)

    # TODO build / run
