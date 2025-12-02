import pytest

from arcor2.data import common
from arcor2.data.rpc import get_id
from arcor2.object_types.abstract import Generic, GenericWithPose
from arcor2_arserver.tests.testutils import event, lock_object, unlock_object
from arcor2_arserver_data import events, objects, rpc
from arcor2_arserver_data.client import ARServer

pytest_plugins = ["pytest_asyncio", "arcor2_arserver.tests.testutils"]


@pytest.fixture
def scene(ars: ARServer) -> common.Scene:
    assert isinstance(ars.get_event(), events.c.ShowMainScreen)

    test = "Test scene"

    assert ars.call_rpc(
        rpc.s.NewScene.Request(get_id(), rpc.s.NewScene.Request.Args(test, test)), rpc.s.NewScene.Response
    ).result

    scene_evt = event(ars, events.s.OpenScene)
    assert scene_evt.data

    event(ars, events.s.SceneState)

    test_type = "TestType"

    assert ars.call_rpc(
        rpc.o.NewObjectType.Request(get_id(), objects.ObjectTypeMeta(test_type, base=Generic.__name__)),
        rpc.o.NewObjectType.Response,
    ).result

    tt_evt = event(ars, events.o.ChangedObjectTypes)

    assert len(tt_evt.data) == 1
    assert not tt_evt.data[0].has_pose
    assert tt_evt.data[0].type == test_type
    assert tt_evt.data[0].base == Generic.__name__

    assert ars.call_rpc(
        rpc.s.AddObjectToScene.Request(get_id(), rpc.s.AddObjectToScene.Request.Args("test_type", test_type)),
        rpc.s.AddObjectToScene.Response,
    ).result

    event(ars, events.s.SceneObjectChanged)

    test_type_with_pose = "TestTypeWithPose"

    assert ars.call_rpc(
        rpc.o.NewObjectType.Request(
            get_id(), objects.ObjectTypeMeta(test_type_with_pose, base=GenericWithPose.__name__)
        ),
        rpc.o.NewObjectType.Response,
    ).result

    ttwp_evt = event(ars, events.o.ChangedObjectTypes)
    assert len(ttwp_evt.data) == 1
    assert ttwp_evt.data[0].has_pose
    assert ttwp_evt.data[0].type == test_type_with_pose
    assert ttwp_evt.data[0].base == GenericWithPose.__name__

    assert ars.call_rpc(
        rpc.s.AddObjectToScene.Request(get_id(), rpc.s.AddObjectToScene.Request.Args("test_type_with_pose", test_type)),
        rpc.s.AddObjectToScene.Response,
    ).result

    event(ars, events.s.SceneObjectChanged)

    assert ars.call_rpc(rpc.s.SaveScene.Request(get_id()), rpc.s.SaveScene.Response).result
    event(ars, events.s.SceneSaved)
    assert ars.call_rpc(rpc.s.CloseScene.Request(get_id()), rpc.s.CloseScene.Response).result
    event(ars, events.s.SceneClosed)
    event(ars, events.c.ShowMainScreen)

    return scene_evt.data.scene


@pytest.fixture
def project(ars: ARServer, scene: common.Scene) -> common.Project:
    """Creates project with following objects:

    ap - global AP
    ap_ap - child of ap
    ap_ap_ap - child of ap_ap
    ori - ap_ap_ap orientation
    """

    test = "Test project"

    assert ars.call_rpc(
        rpc.p.NewProject.Request(get_id(), rpc.p.NewProject.Request.Args(scene.id, test, test)),
        rpc.p.NewProject.Response,
    ).result

    project_evt = event(ars, events.p.OpenProject)
    assert project_evt.data

    event(ars, events.s.SceneState)

    assert ars.call_rpc(
        rpc.p.AddActionPoint.Request(get_id(), rpc.p.AddActionPoint.Request.Args("ap", common.Position(0, 0, 0))),
        rpc.p.AddActionPoint.Response,
    ).result
    ap_evt = event(ars, events.p.ActionPointChanged)
    assert ap_evt.data

    assert ars.call_rpc(
        rpc.p.AddActionPoint.Request(
            get_id(), rpc.p.AddActionPoint.Request.Args("ap_ap", common.Position(0, 0, 1), ap_evt.data.id)
        ),
        rpc.p.AddActionPoint.Response,
    ).result
    ap_ap_evt = event(ars, events.p.ActionPointChanged)
    assert ap_ap_evt.data

    assert ars.call_rpc(
        rpc.p.AddActionPoint.Request(
            get_id(), rpc.p.AddActionPoint.Request.Args("ap_ap_ap", common.Position(0, 0, 2), ap_ap_evt.data.id)
        ),
        rpc.p.AddActionPoint.Response,
    ).result
    ap_ap_ap_evt = event(ars, events.p.ActionPointChanged)
    assert ap_ap_ap_evt.data

    lock_object(ars, ap_ap_ap_evt.data.id)

    assert ars.call_rpc(
        rpc.p.AddActionPointOrientation.Request(
            get_id(), rpc.p.AddActionPointOrientation.Request.Args(ap_ap_ap_evt.data.id, common.Orientation(), "ori")
        ),
        rpc.p.AddActionPointOrientation.Response,
    ).result
    ori_evt = event(ars, events.p.OrientationChanged)
    assert ori_evt.data

    unlock_object(ars, ap_ap_ap_evt.data.id)

    assert ars.call_rpc(rpc.p.SaveProject.Request(get_id()), rpc.p.SaveProject.Response).result
    event(ars, events.p.ProjectSaved)
    assert ars.call_rpc(rpc.p.CloseProject.Request(get_id()), rpc.p.CloseProject.Response).result
    event(ars, events.p.ProjectClosed)
    event(ars, events.c.ShowMainScreen)

    return project_evt.data.project
