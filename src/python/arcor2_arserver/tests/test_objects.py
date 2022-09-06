import pytest

from arcor2.data.common import Pose
from arcor2.data.object_type import Box, Cylinder, Mesh, Model3dType, ObjectModel, Sphere
from arcor2.object_types.abstract import CollisionObject
from arcor2.object_types.upload import upload_def
from arcor2.test_objects.box import Box as BoxType
from arcor2.test_objects.dummy_multiarm_robot import DummyMultiArmRobot
from arcor2_arserver.tests.testutils import event, lock_object, project_service, unlock_object
from arcor2_arserver_data import events, objects, rpc
from arcor2_arserver_data.client import ARServer, get_id

mesh_filename = "test_type.dae"


# TODO find out way how to test invalid models (has to be constructed as a json)
@pytest.mark.parametrize(
    "model",
    [
        ObjectModel(Model3dType.BOX, box=Box("", 1, 1, 1)),
        ObjectModel(Model3dType.BOX, box=Box("", 0, 1, 1)),
        ObjectModel(Model3dType.SPHERE, sphere=Sphere("", 1)),
        ObjectModel(Model3dType.CYLINDER, cylinder=Cylinder("", 1, 1)),
        ObjectModel(Model3dType.MESH, mesh=Mesh("", mesh_filename, [Pose(), Pose()])),
        ObjectModel(Model3dType.MESH, mesh=Mesh("", mesh_filename, [])),
        ObjectModel(Model3dType.MESH, mesh=Mesh("", mesh_filename)),
    ],
)
def test_valid_object_types(start_processes: None, ars: ARServer, model: ObjectModel) -> None:

    event(ars, events.c.ShowMainScreen)

    type_name = "TestType"

    model.model().id = type_name

    if model.mesh:
        project_service.upload_file(mesh_filename, b"")

    assert ars.call_rpc(
        rpc.o.NewObjectType.Request(
            get_id(), objects.ObjectTypeMeta(type_name, base=CollisionObject.__name__, object_model=model)
        ),
        rpc.o.NewObjectType.Response,
    ).result

    evt = event(ars, events.o.ChangedObjectTypes)

    assert len(evt.data) == 1
    assert evt.data[0].has_pose
    assert evt.data[0].type == type_name
    assert evt.data[0].base == CollisionObject.__name__
    assert evt.data[0].object_model == model

    project_service.get_model(model.model().id, model.type)
    project_service.get_object_type(type_name)


def test_update_object_model(start_processes: None, ars: ARServer) -> None:

    upload_def(BoxType, Box(BoxType.__name__, 0.1, 0.1, 0.1))
    upload_def(DummyMultiArmRobot)

    event(ars, events.c.ShowMainScreen)

    assert ars.call_rpc(
        rpc.s.NewScene.Request(get_id(), rpc.s.NewScene.Request.Args("TestScene")), rpc.s.NewScene.Response
    ).result

    assert len(event(ars, events.o.ChangedObjectTypes).data) == 2

    event(ars, events.s.OpenScene)
    event(ars, events.s.SceneState)

    lock_object(ars, BoxType.__name__)

    om = ObjectModel(Model3dType.SPHERE, sphere=Sphere(BoxType.__name__, 0.1))

    assert ars.call_rpc(
        rpc.o.UpdateObjectModel.Request(get_id(), rpc.o.UpdateObjectModel.Request.Args(BoxType.__name__, om)),
        rpc.o.UpdateObjectModel.Response,
    ).result

    ot_evt = event(ars, events.o.ChangedObjectTypes)
    assert ot_evt.change_type == ot_evt.Type.UPDATE
    assert len(ot_evt.data) == 1
    assert ot_evt.data[0].object_model == om
    assert ot_evt.data[0].type == BoxType.__name__
    assert ot_evt.data[0].has_pose
    assert not ot_evt.data[0].disabled

    assert BoxType.__name__ in {obj.id for obj in project_service.get_object_type_ids()}
    assert BoxType.__name__ in {mod.id for mod in project_service.get_models()}

    unlock_object(ars, BoxType.__name__)

    lock_object(ars, DummyMultiArmRobot.__name__)

    assert not ars.call_rpc(
        rpc.o.UpdateObjectModel.Request(
            get_id(),
            rpc.o.UpdateObjectModel.Request.Args(
                DummyMultiArmRobot.__name__,
                ObjectModel(Model3dType.SPHERE, sphere=Sphere(DummyMultiArmRobot.__name__, 0.1)),
            ),
        ),
        rpc.o.UpdateObjectModel.Response,
    ).result

    unlock_object(ars, DummyMultiArmRobot.__name__)

    delete_res_1 = ars.call_rpc(
        rpc.o.DeleteObjectTypes.Request(get_id(), {BoxType.__name__}, dry_run=True),
        rpc.o.DeleteObjectTypes.Response,
    )

    assert delete_res_1.result
    assert delete_res_1.data is None

    delete_res_2 = ars.call_rpc(
        rpc.o.DeleteObjectTypes.Request(get_id(), {BoxType.__name__}),
        rpc.o.DeleteObjectTypes.Response,
    )

    assert delete_res_2.result
    assert delete_res_2.data is None

    ot_evt2 = event(ars, events.o.ChangedObjectTypes)
    assert ot_evt2.change_type == ot_evt.Type.REMOVE
    assert len(ot_evt2.data) == 1
    assert ot_evt2.data[0].object_model == om
    assert ot_evt2.data[0].type == BoxType.__name__

    assert BoxType.__name__ not in {obj.id for obj in project_service.get_object_type_ids()}
    assert BoxType.__name__ not in {mod.id for mod in project_service.get_models()}
