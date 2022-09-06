import pytest

from arcor2.data.rpc.common import TypeArgs
from arcor2_arserver_data import events, rpc
from arcor2_arserver_data.client import ARServer, get_id
from arcor2_logger.object_types.logging_test_object import LoggingTestObject
from arcor2_logger.object_types.logging_test_robot import LoggingTestRobot


@pytest.mark.additional_deps(["./src.python.arcor2_logger.scripts/upload_objects.pex"])
def test_objects(start_processes: None, ars: ARServer) -> None:

    assert isinstance(ars.get_event(), events.c.ShowMainScreen)

    res = ars.call_rpc(rpc.o.GetObjectTypes.Request(get_id()), rpc.o.GetObjectTypes.Response)
    assert res.result
    assert res.data is not None

    assert {obj.type for obj in res.data if not obj.built_in} == {LoggingTestObject.__name__, LoggingTestRobot.__name__}

    for obj in res.data:
        assert not obj.disabled, f"ObjectType {obj.type} disabled. {obj.problem}"

        actions = ars.call_rpc(rpc.o.GetActions.Request(get_id(), TypeArgs(obj.type)), rpc.o.GetActions.Response)
        assert actions.result
        assert actions.data is not None

        for act in actions.data:
            assert act.disabled == (act.problem is not None)
            assert not act.disabled, f"Action {act.name} of {obj.type} disabled. {act.problem}"
