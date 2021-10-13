from dataclasses import dataclass

from arcor2 import json
from arcor2.data.common import Action, ActionParameter, Flow, Orientation, Pose, Position
from arcor2.data.events import Event
from arcor2.data.object_type import Box as BoxModel
from arcor2.object_types.upload import upload_def
from arcor2.parameter_plugins.pose import PosePlugin
from arcor2.test_objects.box import Box
from arcor2_arserver.tests.conftest import event, lock_object, unlock_object
from arcor2_arserver_data import events, rpc
from arcor2_arserver_data.client import ARServer, get_id


@dataclass
class ActionChanged(Event):
    data: Action


def test_project_ap_rpcs(start_processes: None, ars: ARServer) -> None:

    upload_def(Box, BoxModel(Box.__name__, 1, 2, 3))

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
        rpc.s.AddObjectToScene.Request(get_id(), rpc.s.AddObjectToScene.Request.Args("box", Box.__name__, Pose())),
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
    event(ars, events.p.OpenProject)
    event(ars, events.s.SceneState)

    assert ars.call_rpc(
        rpc.p.AddActionPoint.Request(get_id(), rpc.p.AddActionPoint.Request.Args("parent_ap", Position())),
        rpc.p.AddActionPoint.Response,
    ).result

    parent_ap_evt = event(ars, events.p.ActionPointChanged)

    assert ars.call_rpc(
        rpc.p.AddActionPoint.Request(
            get_id(), rpc.p.AddActionPoint.Request.Args("child_ap", Position(-1), parent_ap_evt.data.id)
        ),
        rpc.p.AddActionPoint.Response,
    ).result

    child_ap_evt = event(ars, events.p.ActionPointChanged)
    assert child_ap_evt.data.parent == parent_ap_evt.data.id

    lock_object(ars, child_ap_evt.data.id)

    assert ars.call_rpc(
        rpc.p.AddActionPointOrientation.Request(
            get_id(), rpc.p.AddActionPointOrientation.Request.Args(child_ap_evt.data.id, Orientation())
        ),
        rpc.p.AddActionPointOrientation.Response,
    ).result

    ori = event(ars, events.p.OrientationChanged)

    assert ars.call_rpc(
        rpc.p.AddAction.Request(
            get_id(),
            rpc.p.AddAction.Request.Args(
                child_ap_evt.data.id,
                "act_name",
                f"{obj.id}/{Box.update_pose.__name__}",
                [ActionParameter("new_pose", PosePlugin.type_name(), json.dumps(ori.data.id))],
                [Flow()],
            ),
        ),
        rpc.p.AddAction.Response,
    ).result

    event(ars, events.p.ActionChanged)

    unlock_object(ars, child_ap_evt.data.id)

    ars.event_mapping[ActionChanged.__name__] = ActionChanged

    assert ars.call_rpc(
        rpc.p.CopyActionPoint.Request(get_id(), rpc.p.CopyActionPoint.Request.Args(parent_ap_evt.data.id)),
        rpc.p.CopyActionPoint.Response,
    ).result

    new_parent_ap = event(ars, events.p.ActionPointChanged)
    assert not new_parent_ap.data.parent

    new_child_ap = event(ars, events.p.ActionPointChanged)
    assert new_child_ap.data.parent == new_parent_ap.data.id

    new_ori = event(ars, events.p.OrientationChanged)
    assert new_ori.parent_id == new_child_ap.data.id

    # with events.p.ActionChanged it would return only BareAction (without parameters)
    new_action = event(ars, ActionChanged)
    ars.event_mapping[ActionChanged.__name__] = events.p.ActionChanged
    assert new_action.parent_id == new_child_ap.data.id

    # Pose parameter (orientation id) should be updated now
    assert len(new_action.data.parameters) == 1
    assert json.loads(new_action.data.parameters[0].value) == new_ori.data.id
