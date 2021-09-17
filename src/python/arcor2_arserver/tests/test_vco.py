from arcor2.data.common import Pose
from arcor2.data.object_type import Box, ObjectModel
from arcor2_arserver.tests.conftest import event, project_service
from arcor2_arserver_data import events, rpc
from arcor2_arserver_data.client import ARServer, get_id


def test_virtual_collision_object(start_processes: None, ars: ARServer) -> None:
    event(ars, events.c.ShowMainScreen)

    assert ars.call_rpc(
        rpc.s.NewScene.Request(get_id(), rpc.s.NewScene.Request.Args("TestScene")), rpc.s.NewScene.Response
    ).result

    event(ars, events.s.OpenScene)
    event(ars, events.s.SceneState)

    name = "vco"
    box = Box(name, 0.1, 0.1, 0.1)
    om = ObjectModel(box.type(), box=box)

    add_vco = ars.call_rpc(
        rpc.s.AddVirtualCollisionObjectToScene.Request(
            get_id(), rpc.s.AddVirtualCollisionObjectToScene.Request.Args(name, Pose(), om)
        ),
        rpc.s.AddVirtualCollisionObjectToScene.Response,
    )

    ot = project_service.get_object_type(name)
    assert ot.source

    assert add_vco.result

    ot_evt = event(ars, events.o.ChangedObjectTypes)
    assert ot_evt.change_type == ot_evt.Type.ADD
    assert len(ot_evt.data) == 1
    assert ot_evt.data[0].object_model == om
    assert ot_evt.data[0].type == name

    scn_evt = event(ars, events.s.SceneObjectChanged)
    assert scn_evt.change_type == ot_evt.Type.ADD
    assert scn_evt.data.name == name

    assert ars.call_rpc(
        rpc.s.StartScene.Request(get_id()),
        rpc.s.StartScene.Response,
    ).result

    assert event(ars, events.s.SceneState).data.state == events.s.SceneState.Data.StateEnum.Starting
    assert event(ars, events.s.SceneState).data.state == events.s.SceneState.Data.StateEnum.Started

    assert ars.call_rpc(
        rpc.s.StopScene.Request(get_id()),
        rpc.s.StopScene.Response,
    ).result

    assert event(ars, events.s.SceneState).data.state == events.s.SceneState.Data.StateEnum.Stopping
    assert event(ars, events.s.SceneState).data.state == events.s.SceneState.Data.StateEnum.Stopped

    delete_res_2 = ars.call_rpc(
        rpc.s.RemoveFromScene.Request(get_id(), rpc.s.RemoveFromScene.Request.Args(scn_evt.data.id)),
        rpc.s.RemoveFromScene.Response,
    )

    assert delete_res_2.result

    scn_evt2 = event(ars, events.s.SceneObjectChanged)
    assert scn_evt2.change_type == ot_evt.Type.REMOVE
    assert scn_evt2.data.name == name

    assert ars.call_rpc(
        rpc.s.SaveScene.Request(get_id()),
        rpc.s.SaveScene.Response,
    ).result

    assert event(ars, events.s.SceneSaved)

    ot_evt2 = event(ars, events.o.ChangedObjectTypes)
    assert ot_evt2.change_type == ot_evt2.Type.REMOVE
    assert len(ot_evt2.data) == 1
    assert ot_evt2.data[0].object_model == om
    assert ot_evt2.data[0].type == name

    assert name not in {ot.id for ot in project_service.get_object_type_ids()}
