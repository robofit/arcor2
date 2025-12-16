import json

from arcor2.data.common import Parameter, Scene
from arcor2.data.rpc.common import IdArgs
from arcor2_arserver.tests.objects.object_with_settings import ObjectWithSettings
from arcor2_arserver.tests.testutils import event, lock_object, save_project, unlock_object
from arcor2_arserver_data import events, rpc
from arcor2_arserver_data.client import ARServer, get_id
from arcor2_object_types.upload import upload_def


def test_object_parameters(start_processes: None, ars: ARServer, scene: Scene) -> None:
    upload_def(ObjectWithSettings)

    assert ars.call_rpc(rpc.s.OpenScene.Request(get_id(), IdArgs(scene.id)), rpc.s.OpenScene.Response).result

    assert len(event(ars, events.o.ChangedObjectTypes).data) == 1

    event(ars, events.s.OpenScene)
    event(ars, events.s.SceneState)

    req_params = [  # TODO create settings_to_params and use it
        Parameter("str_param", "string", json.dumps("str_param")),
        Parameter("float_param", "double", json.dumps(1.0)),
        Parameter("int_param", "integer", json.dumps(1)),
        Parameter("bool_param", "boolean", json.dumps(True)),
    ]

    assert ars.call_rpc(
        rpc.s.AddObjectToScene.Request(
            get_id(), rpc.s.AddObjectToScene.Request.Args("ows", ObjectWithSettings.__name__, parameters=req_params)
        ),
        rpc.s.AddObjectToScene.Response,
    ).result

    soc = event(ars, events.s.SceneObjectChanged)
    assert soc.change_type
    assert soc.change_type == soc.change_type.ADD
    assert soc.data.type == ObjectWithSettings.__name__
    assert soc.data.parameters == req_params
    obj_id = soc.data.id

    req_params2 = [  # TODO create settings_to_params and use it
        Parameter("str_param", "string", json.dumps("str_param2")),
        Parameter("float_param", "double", json.dumps(2.0)),
        Parameter("int_param", "integer", json.dumps(2)),
        Parameter("bool_param", "boolean", json.dumps(True)),
    ]

    lock_object(ars, soc.data.id)

    assert ars.call_rpc(
        rpc.s.UpdateObjectParameters.Request(
            get_id(), rpc.s.UpdateObjectParameters.Request.Args(soc.data.id, parameters=req_params2)
        ),
        rpc.s.AddObjectToScene.Response,
    ).result

    soc2 = event(ars, events.s.SceneObjectChanged)
    assert soc2.change_type == soc.change_type.UPDATE
    assert soc2.data.type == ObjectWithSettings.__name__
    assert soc2.data.parameters == req_params2

    unlock_object(ars, soc.data.id)

    # let's continue with testing overrides
    assert ars.call_rpc(
        rpc.p.NewProject.Request(get_id(), rpc.p.NewProject.Request.Args(scene.id, "Project name")),
        rpc.p.NewProject.Response,
    ).result

    event(ars, events.s.SceneSaved)
    event(ars, events.p.OpenProject)
    event(ars, events.s.SceneState)

    assert not ars.call_rpc(
        rpc.o.DeleteOverride.Request(
            get_id(), rpc.o.DeleteOverride.Request.Args(obj_id, Parameter("bool_param", "boolean", json.dumps(True)))
        ),
        rpc.o.DeleteOverride.Response,
    ).result

    assert not ars.call_rpc(
        rpc.o.UpdateOverride.Request(
            get_id(), rpc.o.UpdateOverride.Request.Args(obj_id, Parameter("bool_param", "boolean", json.dumps(True)))
        ),
        rpc.o.UpdateOverride.Response,
    ).result

    # int_param has to be set to special value, so without override, StartScene should fail now
    assert ars.call_rpc(
        rpc.s.StartScene.Request(get_id()),
        rpc.s.StartScene.Response,
    ).result

    assert event(ars, events.s.SceneState).data.state == events.s.SceneState.Data.StateEnum.Starting
    assert event(ars, events.s.SceneState).data.state == events.s.SceneState.Data.StateEnum.Stopping
    assert event(ars, events.s.SceneState).data.state == events.s.SceneState.Data.StateEnum.Stopped

    lock_object(ars, obj_id)

    override = Parameter("int_param", "integer", json.dumps(ObjectWithSettings.INT_PARAM_SPECIAL_VALUE))

    assert ars.call_rpc(
        rpc.o.AddOverride.Request(get_id(), rpc.o.AddOverride.Request.Args(obj_id, override)),
        rpc.o.AddOverride.Response,
    ).result

    override_evt = event(ars, events.o.OverrideUpdated)
    assert override_evt.data == override
    assert override_evt.change_type
    assert override_evt.change_type == override_evt.change_type.ADD
    assert override_evt.parent_id == obj_id

    override2 = Parameter("str_param", "string", json.dumps("test"))

    assert ars.call_rpc(
        rpc.o.AddOverride.Request(get_id(), rpc.o.AddOverride.Request.Args(obj_id, override2)),
        rpc.o.AddOverride.Response,
    ).result

    event(ars, events.o.OverrideUpdated)

    unlock_object(ars, obj_id)

    save_project(ars)

    # now it should be possible to start the scene
    assert ars.call_rpc(
        rpc.s.StartScene.Request(get_id()),
        rpc.s.StartScene.Response,
    ).result

    assert event(ars, events.s.SceneState).data.state == events.s.SceneState.Data.StateEnum.Starting
    assert event(ars, events.s.SceneState).data.state == events.s.SceneState.Data.StateEnum.Started
