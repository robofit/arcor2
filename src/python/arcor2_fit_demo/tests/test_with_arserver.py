import pytest

from arcor2.data.rpc.common import TypeArgs
from arcor2_arserver_data import events, rpc
from arcor2_arserver_data.client import ARServer, get_id
from arcor2_arserver_data.robot import RobotMeta
from arcor2_fit_demo.object_types.dobot_m1 import DobotM1
from arcor2_fit_demo.object_types.dobot_magician import DobotMagician


@pytest.mark.additional_deps([["src.python.arcor2_fit_demo.scripts/upload_objects.pex"]])
def test_objects(start_processes: None, ars: ARServer) -> None:

    assert isinstance(ars.get_event(), events.c.ShowMainScreen)

    res = ars.call_rpc(rpc.o.GetObjectTypes.Request(get_id()), rpc.o.GetObjectTypes.Response)
    assert res.result
    assert res.data is not None

    for obj in res.data:
        assert not obj.disabled, f"ObjectType {obj.type} disabled. {obj.problem}"

        actions = ars.call_rpc(rpc.o.GetActions.Request(get_id(), TypeArgs(obj.type)), rpc.o.GetActions.Response)
        assert actions.result
        assert actions.data is not None

        for act in actions.data:
            assert act.disabled == (act.problem is not None)
            assert not act.disabled, f"Action {act.name} of {obj.type} disabled. {act.problem}"

    res2 = ars.call_rpc(rpc.r.GetRobotMeta.Request(get_id()), rpc.r.GetRobotMeta.Response)
    assert res2.result
    assert res2.data is not None

    robots: dict[str, RobotMeta] = {robot.type: robot for robot in res2.data}

    magician = robots[DobotMagician.__name__]
    assert magician.features.move_to_pose
    assert magician.features.move_to_joints
    assert magician.features.inverse_kinematics
    assert magician.features.forward_kinematics
    assert not magician.features.stop
    assert not magician.features.hand_teaching

    m1 = robots[DobotM1.__name__]
    assert m1.features.move_to_pose
    assert m1.features.move_to_joints
    assert m1.features.hand_teaching
    assert not m1.features.inverse_kinematics
    assert not m1.features.forward_kinematics
    assert not m1.features.stop
