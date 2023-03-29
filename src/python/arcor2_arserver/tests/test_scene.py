from arcor2.clients import project_service
from arcor2.data.common import Pose, Position, Project, Scene, SceneObject
from arcor2.data.events import Event
from arcor2.data.object_type import Box as BoxModel
from arcor2.data.rpc.common import IdArgs
from arcor2.object_types.upload import upload_def
from arcor2.test_objects.box import Box
from arcor2.test_objects.dummy_multiarm_robot import DummyMultiArmRobot
from arcor2_arserver.tests.testutils import ars_connection_str, event, event_mapping, lock_object, unlock_object
from arcor2_arserver_data import events, rpc
from arcor2_arserver_data.client import ARServer, get_id


def test_scene_basic_rpcs(start_processes: None, ars: ARServer) -> None:
    test = "Test"

    # initial event
    show_main_screen_event = event(ars, events.c.ShowMainScreen)
    assert show_main_screen_event.data
    assert show_main_screen_event.data.what == events.c.ShowMainScreen.Data.WhatEnum.ScenesList

    # first, there are no scenes
    scenes = ars.call_rpc(rpc.s.ListScenes.Request(get_id()), rpc.s.ListScenes.Response)
    assert scenes.result
    assert not scenes.data

    assert ars.call_rpc(
        rpc.s.NewScene.Request(get_id(), rpc.s.NewScene.Request.Args(test, test)), rpc.s.NewScene.Response
    ).result

    open_scene_event = event(ars, events.s.OpenScene)
    assert open_scene_event.parent_id is None
    assert open_scene_event.change_type is None
    assert open_scene_event.data
    assert open_scene_event.data.scene.id
    scene_id = open_scene_event.data.scene.id
    assert open_scene_event.data.scene.name == test
    assert open_scene_event.data.scene.description == test
    assert not open_scene_event.data.scene.objects

    event(ars, events.s.SceneState)

    # attempt to create a new scene while scene is open should fail
    assert not ars.call_rpc(
        rpc.s.NewScene.Request(get_id(), rpc.s.NewScene.Request.Args(test, test)), rpc.s.NewScene.Response
    ).result

    assert ars.call_rpc(rpc.s.SaveScene.Request(get_id()), rpc.s.SaveScene.Response).result

    event(ars, events.s.SceneSaved)

    assert ars.call_rpc(rpc.s.CloseScene.Request(get_id()), rpc.s.CloseScene.Response).result

    event(ars, events.s.SceneClosed)

    show_main_screen_event_2 = event(ars, events.c.ShowMainScreen)
    assert show_main_screen_event_2.data
    assert show_main_screen_event_2.data.what == events.c.ShowMainScreen.Data.WhatEnum.ScenesList
    assert show_main_screen_event_2.data.highlight == scene_id

    # attempt to open non-existent scene
    assert not ars.call_rpc(
        rpc.s.OpenScene.Request(get_id(), IdArgs("some-random-nonsense")), rpc.s.OpenScene.Response
    ).result

    list_of_scenes = ars.call_rpc(rpc.s.ListScenes.Request(get_id()), rpc.s.ListScenes.Response)
    assert list_of_scenes.result
    assert list_of_scenes.data
    assert len(list_of_scenes.data) == 1
    assert list_of_scenes.data[0].id == scene_id

    # open previously saved scene
    assert ars.call_rpc(rpc.s.OpenScene.Request(get_id(), IdArgs(scene_id)), rpc.s.OpenScene.Response).result

    open_scene_event_2 = event(ars, events.s.OpenScene)
    assert open_scene_event_2.data
    assert open_scene_event_2.data.scene.id == scene_id

    event(ars, events.s.SceneState)

    assert ars.call_rpc(rpc.s.CloseScene.Request(get_id()), rpc.s.CloseScene.Response).result
    event(ars, events.s.SceneClosed)

    show_main_screen_event_3 = event(ars, events.c.ShowMainScreen)
    assert show_main_screen_event_3.data
    assert show_main_screen_event_3.data.what == events.c.ShowMainScreen.Data.WhatEnum.ScenesList
    assert show_main_screen_event_3.data.highlight == scene_id

    with ARServer(ars_connection_str(), timeout=10, event_mapping=event_mapping) as ars_2:
        smse = event(ars_2, events.c.ShowMainScreen)
        assert smse.data
        assert smse.data.what == events.c.ShowMainScreen.Data.WhatEnum.ScenesList
        assert smse.data.highlight is None

    assert ars.call_rpc(rpc.s.DeleteScene.Request(get_id(), IdArgs(scene_id)), rpc.s.DeleteScene.Response).result

    scene_changed_evt = event(ars, events.s.SceneChanged)
    assert scene_changed_evt.data
    assert scene_changed_evt.data.id == scene_id
    assert scene_changed_evt.change_type == Event.Type.REMOVE

    list_of_scenes_2 = ars.call_rpc(rpc.s.ListScenes.Request(get_id()), rpc.s.ListScenes.Response)
    assert list_of_scenes_2.result
    assert not list_of_scenes_2.data


def test_update_object_pose(start_processes: None, ars: ARServer) -> None:
    upload_def(Box, BoxModel("Box", 0.1, 0.1, 0.1))
    upload_def(DummyMultiArmRobot)

    test = "test"

    event(ars, events.c.ShowMainScreen)

    assert ars.call_rpc(
        rpc.s.NewScene.Request(get_id(), rpc.s.NewScene.Request.Args(test)), rpc.s.NewScene.Response
    ).result

    assert len(event(ars, events.o.ChangedObjectTypes).data) == 2

    event(ars, events.s.OpenScene)
    event(ars, events.s.SceneState)

    assert ars.call_rpc(
        rpc.s.AddObjectToScene.Request(get_id(), rpc.s.AddObjectToScene.Request.Args("obj", Box.__name__, Pose())),
        rpc.s.AddObjectToScene.Response,
    ).result

    scene_obj = event(ars, events.s.SceneObjectChanged).data

    assert ars.call_rpc(
        rpc.s.AddObjectToScene.Request(
            get_id(), rpc.s.AddObjectToScene.Request.Args("robot", DummyMultiArmRobot.__name__, Pose())
        ),
        rpc.s.AddObjectToScene.Response,
    ).result

    scene_robot = event(ars, events.s.SceneObjectChanged).data

    new_pose = Pose(Position(1))

    lock_object(ars, scene_obj.id)

    assert ars.call_rpc(
        rpc.s.UpdateObjectPose.Request(get_id(), rpc.s.UpdateObjectPose.Request.Args(scene_obj.id, new_pose)),
        rpc.s.UpdateObjectPose.Response,
    ).result

    assert event(ars, events.s.SceneObjectChanged).data.pose == new_pose
    unlock_object(ars, scene_obj.id)

    lock_object(ars, scene_robot.id)

    assert ars.call_rpc(
        rpc.s.UpdateObjectPose.Request(get_id(), rpc.s.UpdateObjectPose.Request.Args(scene_robot.id, new_pose)),
        rpc.s.UpdateObjectPose.Response,
    ).result

    assert event(ars, events.s.SceneObjectChanged).data.pose == new_pose
    unlock_object(ars, scene_robot.id)

    assert ars.call_rpc(
        rpc.s.StartScene.Request(get_id()),
        rpc.s.StartScene.Response,
    ).result

    assert event(ars, events.s.SceneState).data.state == events.s.SceneState.Data.StateEnum.Starting
    assert event(ars, events.s.SceneState).data.state == events.s.SceneState.Data.StateEnum.Started

    lock_object(ars, scene_obj.id)

    # with started scene, it should still be possible to manipulate the object
    assert ars.call_rpc(
        rpc.s.UpdateObjectPose.Request(get_id(), rpc.s.UpdateObjectPose.Request.Args(scene_obj.id, Pose())),
        rpc.s.UpdateObjectPose.Response,
    ).result

    assert event(ars, events.s.SceneObjectChanged).data.pose == Pose()
    unlock_object(ars, scene_obj.id)

    lock_object(ars, scene_robot.id)

    # ...but it should not be possible to manipulate the robot
    assert not ars.call_rpc(
        rpc.s.UpdateObjectPose.Request(get_id(), rpc.s.UpdateObjectPose.Request.Args(scene_robot.id, Pose())),
        rpc.s.UpdateObjectPose.Response,
    ).result

    unlock_object(ars, scene_robot.id)


def test_list_problems(start_processes: None, ars: ARServer) -> None:
    """This is a test for a bug in get_scene_problems and get_project_problems
    functions.

    Because of the bug, the RPC returned result=False when there was non-existing ObjectType.

    :param start_processes:
    :param ars:
    :return:
    """

    upload_def(DummyMultiArmRobot)  # OT has to exist first, otherwise scene can't be stored
    invalid_scene_1 = Scene("invalidScene", objects=[SceneObject("invalidObject", DummyMultiArmRobot.__name__, Pose())])
    invalid_project_1 = Project("invalidProject", invalid_scene_1.id)
    project_service.update_scene(invalid_scene_1)
    project_service.update_project(invalid_project_1)
    project_service.delete_object_type(DummyMultiArmRobot.__name__)  # now the OT can be deleted

    # initial event
    show_main_screen_event = event(ars, events.c.ShowMainScreen)
    assert show_main_screen_event.data
    assert show_main_screen_event.data.what == events.c.ShowMainScreen.Data.WhatEnum.ScenesList

    scenes = ars.call_rpc(rpc.s.ListScenes.Request(get_id()), rpc.s.ListScenes.Response)
    assert scenes.result
    assert scenes.data
    assert len(scenes.data) == 1
    assert scenes.data[0].id == invalid_scene_1.id
    assert scenes.data[0].name == invalid_scene_1.name
    assert scenes.data[0].problems
    assert len(scenes.data[0].problems) == 1

    projects = ars.call_rpc(rpc.p.ListProjects.Request(get_id()), rpc.p.ListProjects.Response)
    assert projects.result
    assert projects.data
    assert len(projects.data) == 1
    assert projects.data[0].id == invalid_project_1.id
    assert projects.data[0].name == invalid_project_1.name
    assert projects.data[0].problems
    assert len(projects.data[0].problems) == 1

    upload_def(DummyMultiArmRobot)

    # now the ObjectType exists, so the scene/project should be ok
    scenes2 = ars.call_rpc(rpc.s.ListScenes.Request(get_id()), rpc.s.ListScenes.Response)
    assert scenes2.result
    assert scenes2.data
    assert len(scenes2.data) == 1
    assert scenes2.data[0].id == invalid_scene_1.id
    assert scenes2.data[0].name == invalid_scene_1.name
    assert scenes2.data[0].problems is None

    projects2 = ars.call_rpc(rpc.p.ListProjects.Request(get_id()), rpc.p.ListProjects.Response)
    assert projects2.result
    assert projects2.data
    assert len(projects2.data) == 1
    assert projects2.data[0].id == invalid_project_1.id
    assert projects2.data[0].name == invalid_project_1.name
    assert projects2.data[0].problems is None
