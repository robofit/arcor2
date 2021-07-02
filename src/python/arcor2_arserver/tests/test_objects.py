import pytest

from arcor2.data.object_type import Box, Cylinder, Model3dType, ObjectModel, Sphere
from arcor2.object_types.abstract import GenericWithPose
from arcor2_arserver.tests.conftest import event
from arcor2_arserver_data import events, objects, rpc
from arcor2_arserver_data.client import ARServer, get_id


# TODO find out way how to test invalid models (has to be constructed as a json)
@pytest.mark.parametrize(
    "model",
    [
        ObjectModel(Model3dType.BOX, box=Box("", 1, 1, 1)),
        ObjectModel(Model3dType.BOX, box=Box("", 0, 1, 1)),
        ObjectModel(Model3dType.SPHERE, sphere=Sphere("", 1)),
        ObjectModel(Model3dType.CYLINDER, cylinder=Cylinder("", 1, 1)),
    ],
)
def test_valid_object_types(start_processes: None, ars: ARServer, model: ObjectModel) -> None:

    event(ars, events.c.ShowMainScreen)

    type_name = "TestType"

    model.model().id = type_name

    assert ars.call_rpc(
        rpc.o.NewObjectType.Request(
            get_id(), objects.ObjectTypeMeta(type_name, base=GenericWithPose.__name__, object_model=model)
        ),
        rpc.o.NewObjectType.Response,
    ).result

    evt = event(ars, events.o.ChangedObjectTypes)

    assert len(evt.data) == 1
    assert evt.data[0].has_pose
    assert evt.data[0].type == type_name
    assert evt.data[0].base == GenericWithPose.__name__
    assert evt.data[0].object_model == model
