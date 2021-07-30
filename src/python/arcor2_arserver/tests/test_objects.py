import pytest

from arcor2.data.common import Pose
from arcor2.data.object_type import Box, Cylinder, Mesh, Model3dType, ObjectModel, Sphere
from arcor2.object_types.abstract import CollisionObject
from arcor2_arserver.tests.conftest import event, project_service
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
