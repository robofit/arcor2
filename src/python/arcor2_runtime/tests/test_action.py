import importlib
import io
import threading
import time

import pytest

from arcor2.data.common import ActionMetadata, Orientation, Pose, Position, ProjectRobotJoints
from arcor2.data.events import ActionStateAfter, ActionStateBefore, PackageState
from arcor2.exceptions import Arcor2Exception
from arcor2.object_types.abstract import Generic
from arcor2_runtime import action as glob_action
from arcor2_runtime.action import ACTION_NAME_ID_MAPPING_ATTR, AP_ID_ATTR, patch_object_actions


def test_patch_object_actions(monkeypatch, capsys) -> None:
    action = importlib.reload(glob_action)  # to get local "copy" of the module

    class MyObject(Generic):
        def action(self, pose: Pose, *, an: None | str = None) -> None:
            pass

        action.__action__ = ActionMetadata()  # type: ignore

    # @action tries to read from stdin
    sio = io.StringIO()
    sio.fileno = lambda: 0  # type: ignore  # fake whatever fileno
    monkeypatch.setattr("sys.stdin", sio)

    obj_id = "123"
    pose = Pose(Position(0, 0, 0), Orientation(1, 0, 0, 0))
    setattr(pose.position, AP_ID_ATTR, "pose")  # set pose id (simulate pose declaration in scene json)

    my_obj = MyObject(obj_id, "")

    thread_id = None  # main thread

    my_obj.action(pose)
    assert not action.g.ea
    out_before, _ = capsys.readouterr()
    assert not out_before

    patch_object_actions(MyObject)
    setattr(MyObject, ACTION_NAME_ID_MAPPING_ATTR, {"name": "id"})  # this simulates what patch_with_action_mapping does

    my_obj.action(pose, an="name")
    assert action.g.ea[thread_id] is None
    out_after, _ = capsys.readouterr()

    arr = out_after.strip().split("\n")
    assert len(arr) == 2

    before_evt = ActionStateBefore.from_json(arr[0])
    after_evt = ActionStateAfter.from_json(arr[1])

    assert before_evt.data.action_id == "id"
    assert after_evt.data.action_id == "id"

    assert before_evt.data.action_point_ids is not None
    assert "pose" in before_evt.data.action_point_ids

    with pytest.raises(Arcor2Exception):
        my_obj.action(pose)

    assert action.g.ea[thread_id] is None

    with pytest.raises(Arcor2Exception):
        my_obj.action(pose, an="unknown_action_name")

    assert action.g.ea[thread_id] is None


def test_patch_object_actions_without_mapping(monkeypatch, capsys) -> None:
    action = importlib.reload(glob_action)  # to get local "copy" of the module

    class MyObject(Generic):
        def action(self, pose: Pose, *, an: None | str = None) -> None:
            pass

        action.__action__ = ActionMetadata()  # type: ignore

    # @action tries to read from stdin
    sio = io.StringIO()
    sio.fileno = lambda: 0  # type: ignore  # fake whatever fileno
    monkeypatch.setattr("sys.stdin", sio)

    obj_id = "123"
    pose = Pose(Position(0, 0, 0), Orientation(1, 0, 0, 0))
    setattr(pose.position, AP_ID_ATTR, "pose")  # set pose id (simulate pose declaration in scene json)

    my_obj = MyObject(obj_id, "")
    thread_id = None
    patch_object_actions(MyObject)  # no mapping given

    my_obj.action(pose)  # this should be ok
    assert action.g.ea[thread_id] is None
    out_after, _ = capsys.readouterr()

    assert out_after

    arr = out_after.strip().split("\n")
    assert len(arr) == 1

    before_evt = ActionStateBefore.from_json(arr[0])

    assert before_evt.data.action_id is None

    assert before_evt.data.parameters
    assert Pose.from_json(before_evt.data.parameters[0]) == pose

    assert before_evt.data.action_point_ids == {"pose"}

    # the 'an' should be just ignored
    # we are testing here that second execution of action is fine
    my_obj.action(pose, an="whatever")
    assert action.g.ea[thread_id] is None
    out_after2, _ = capsys.readouterr()
    assert out_after2 == out_after


def test_composite_action(monkeypatch, capsys) -> None:
    action = importlib.reload(glob_action)  # to get local "copy" of the module

    class MyObject(Generic):
        def inner_inner_action(self, *, an: None | str = None) -> None:
            pass

        def inner_action(self, *, an: None | str = None) -> None:
            self.inner_inner_action()

        def inner_action_2(self, *, an: None | str = None) -> None:
            pass

        def comp_action(self, *, an: None | str = None) -> None:
            self.inner_action()
            self.inner_action_2()

        def action_wo_flag(self, *, an: None | str = None) -> None:
            self.inner_action()
            self.inner_action_2()

        def action_with_inner_name_spec(self, *, an: None | str = None) -> None:
            self.inner_action(an="whatever")

        inner_inner_action.__action__ = ActionMetadata()  # type: ignore
        inner_action.__action__ = ActionMetadata(composite=True)  # type: ignore
        inner_action_2.__action__ = ActionMetadata()  # type: ignore
        comp_action.__action__ = ActionMetadata(composite=True)  # type: ignore
        action_wo_flag.__action__ = ActionMetadata()  # type: ignore
        action_with_inner_name_spec.__action__ = ActionMetadata()  # type: ignore

    # @action tries to read from stdin
    sio = io.StringIO()
    sio.fileno = lambda: 0  # type: ignore  # fake whatever fileno
    monkeypatch.setattr("sys.stdin", sio)

    obj_id = "123"

    my_obj = MyObject(obj_id, "")

    thread_id = None

    my_obj.comp_action()
    assert not action.g.ea
    out_before, _ = capsys.readouterr()
    assert not out_before

    patch_object_actions(MyObject)
    setattr(MyObject, ACTION_NAME_ID_MAPPING_ATTR, {"name": "id"})  # this simulates what patch_with_action_mapping does

    my_obj.comp_action(an="name")
    assert action.g.ea[thread_id] is None
    out_after, _ = capsys.readouterr()

    arr = out_after.strip().split("\n")
    assert len(arr) == 2  # inner actions are ignored

    before_evt = ActionStateBefore.from_json(arr[0])
    after_evt = ActionStateAfter.from_json(arr[1])

    assert before_evt.data.action_id == "id"
    assert after_evt.data.action_id == "id"

    with pytest.raises(Arcor2Exception, match="Mapping from action name to id provided, but action name not set."):
        my_obj.comp_action()

    assert action.g.ea[thread_id] is None

    invalid_an = "unknown_action_name"
    with pytest.raises(Arcor2Exception, match=f"Mapping from action name to id is missing key {invalid_an}."):
        my_obj.comp_action(an=invalid_an)

    assert action.g.ea[thread_id] is None

    with pytest.raises(
        Arcor2Exception, match=f"Outer action {my_obj.action_wo_flag.__name__}/id not flagged as composite."
    ):
        my_obj.action_wo_flag(an="name")

    assert action.g.ea[thread_id] is None

    with pytest.raises(Arcor2Exception, match="Inner actions should not have name specified."):
        my_obj.action_with_inner_name_spec(an="name")

    assert action.g.ea[thread_id] is None


def test_unknown_parameter_type(monkeypatch, capsys) -> None:
    action = importlib.reload(glob_action)  # to get local "copy" of the module

    class UnknownParameterType:
        pass

    class MyObject(Generic):
        def action(self, param: UnknownParameterType, *, an: None | str = None) -> None:
            pass

        action.__action__ = ActionMetadata()  # type: ignore

    # @action tries to read from stdin
    sio = io.StringIO()
    sio.fileno = lambda: 0  # type: ignore  # fake whatever fileno
    monkeypatch.setattr("sys.stdin", sio)

    obj_id = "123"

    my_obj = MyObject(obj_id, "")

    thread_id = None

    patch_object_actions(MyObject)

    # before the mapping is provided, unknown parameter type should be fine
    my_obj.action(UnknownParameterType(), an="name")
    assert action.g.ea[thread_id] is None
    out_after, _ = capsys.readouterr()

    assert out_after
    arr = out_after.strip().split("\n")
    assert len(arr) == 1

    before_evt = ActionStateBefore.from_json(arr[0])
    assert before_evt.data.action_id is None

    setattr(MyObject, ACTION_NAME_ID_MAPPING_ATTR, {"name": "id"})  # this simulates what patch_with_action_mapping does

    # when mapping is provided, attempt to use action with unknown parameter type should fail
    with pytest.raises(Arcor2Exception, match=f"Unknown parameter type {UnknownParameterType.__name__}."):
        my_obj.action(UnknownParameterType(), an="name")

    assert action.g.ea[thread_id] is None


def test_parallel_actions(monkeypatch, capsys) -> None:
    action = importlib.reload(glob_action)  # to get local "copy" of the module

    class ParallelActionsObject(Generic):
        def action1(self, *, an: None | str = None) -> None:
            time.sleep(0.1)

        def action2(self, *, an: None | str = None) -> None:
            time.sleep(0.1)

        action1.__action__ = ActionMetadata()  # type: ignore
        action2.__action__ = ActionMetadata()  # type: ignore

    # @action tries to read from stdin
    sio = io.StringIO()
    sio.fileno = lambda: 0  # type: ignore  # fake whatever fileno
    monkeypatch.setattr("sys.stdin", sio)

    obj_id = "123"

    my_obj = ParallelActionsObject(obj_id, "")

    patch_object_actions(ParallelActionsObject)

    def thread1():
        for _ in range(10):
            my_obj.action1()

    th1 = threading.Thread(target=thread1, daemon=True)
    th1.start()

    for _ in range(10):
        my_obj.action2()

    th1.join()

    assert not action.g.pause.is_set()
    assert not action.g.resume.is_set()
    assert len(action.g.ea) == 2
    assert None in action.g.ea


def test_breakpoints_pose(monkeypatch, capsys) -> None:
    action = importlib.reload(glob_action)  # to get local "copy" of the module

    class ActionObject(Generic):
        def action1(self, pose: Pose, *, an: None | str = None) -> None:
            pass

        action1.__action__ = ActionMetadata()  # type: ignore

    ap1_id = "123"
    pose1 = Pose()
    setattr(pose1.position, AP_ID_ATTR, ap1_id)  # simulates what patch_aps does

    # @action tries to read from stdin
    sio = io.StringIO()
    sio.fileno = lambda: 0  # type: ignore  # fake whatever fileno
    monkeypatch.setattr("sys.stdin", sio)

    obj_id = "123"
    my_obj = ActionObject(obj_id, "")
    patch_object_actions(ActionObject)

    action.g.breakpoints = {ap1_id}

    def thread1():
        my_obj.action1(pose1)

    assert not action.g.pause.is_set()

    th1 = threading.Thread(target=thread1, daemon=True)
    th1.start()

    assert action.g.pause.wait(0.1)

    # maybe it would be better to send command to stdin, but it's a bit complicated
    action.g.resume.set()

    # can't test if action.g.pause was cleared - that is done when reading stdin in _get_commands
    # time.sleep(0.1)
    # assert not action.g.pause.is_set()

    th1.join(0.1)
    assert not th1.is_alive()

    output, _ = capsys.readouterr()
    arr = output.strip().split("\n")
    assert len(arr) == 2

    before_evt = ActionStateBefore.from_json(arr[0])
    assert before_evt.data.action_point_ids == {ap1_id}

    ps_evt = PackageState.from_json(arr[1])
    assert ps_evt.data.state == PackageState.Data.StateEnum.PAUSED


def test_breakpoints_joints(monkeypatch, capsys) -> None:
    action = importlib.reload(glob_action)  # to get local "copy" of the module

    class ActionObject(Generic):
        def action1(self, joints: ProjectRobotJoints, *, an: None | str = None) -> None:
            pass

        action1.__action__ = ActionMetadata()  # type: ignore

    ap1_id = "123"
    joints = ProjectRobotJoints("test_name", "test_robot", [])
    setattr(joints, AP_ID_ATTR, ap1_id)  # simulates what patch_aps does

    # @action tries to read from stdin
    sio = io.StringIO()
    sio.fileno = lambda: 0  # type: ignore  # fake whatever fileno
    monkeypatch.setattr("sys.stdin", sio)

    obj_id = "123"
    my_obj = ActionObject(obj_id, "")
    patch_object_actions(ActionObject)

    action.g.breakpoints = {ap1_id}

    def thread1():
        my_obj.action1(joints)

    assert not action.g.pause.is_set()

    th1 = threading.Thread(target=thread1, daemon=True)
    th1.start()

    assert action.g.pause.wait(0.1)

    # maybe it would be better to send command to stdin, but it's a bit complicated
    action.g.resume.set()

    # can't test if action.g.pause was cleared - that is done when reading stdin in _get_commands
    # time.sleep(0.1)
    # assert not action.g.pause.is_set()

    th1.join(0.1)
    assert not th1.is_alive()

    output, _ = capsys.readouterr()
    arr = output.strip().split("\n")
    assert len(arr) == 2

    before_evt = ActionStateBefore.from_json(arr[0])
    assert before_evt.data.action_point_ids == {ap1_id}

    ps_evt = PackageState.from_json(arr[1])
    assert ps_evt.data.state == PackageState.Data.StateEnum.PAUSED


def test_breakpoints_pose_parallel(monkeypatch, capsys) -> None:
    action = importlib.reload(glob_action)  # to get local "copy" of the module

    class ActionObject(Generic):
        def action1(self, pose: Pose, *, an: None | str = None) -> None:
            pass

        def action2(self, pose: Pose, *, an: None | str = None) -> None:
            pass

        action1.__action__ = ActionMetadata()  # type: ignore
        action2.__action__ = ActionMetadata()  # type: ignore

    ap1_id = "123"
    pose1 = Pose()
    setattr(pose1.position, AP_ID_ATTR, ap1_id)  # simulates what patch_aps does

    ap2_id = "456"
    pose2 = Pose()
    setattr(pose2.position, AP_ID_ATTR, ap2_id)  # simulates what patch_aps does

    # @action tries to read from stdin
    sio = io.StringIO()
    sio.fileno = lambda: 0  # type: ignore  # fake whatever fileno
    monkeypatch.setattr("sys.stdin", sio)

    obj_id = "123"
    my_obj = ActionObject(obj_id, "")
    patch_object_actions(ActionObject)

    action.g.breakpoints = {ap1_id, ap2_id}

    def thread1():
        my_obj.action1(pose1)

    def thread2():
        my_obj.action1(pose2)

    assert not action.g.pause.is_set()

    th1 = threading.Thread(target=thread1, daemon=True)
    th1.start()

    th2 = threading.Thread(target=thread2, daemon=True)
    th2.start()

    assert action.g.pause.wait(0.1)  # hitting breakpoint should result in program being paused

    output, _ = capsys.readouterr()
    arr = output.strip().split("\n")
    assert len(arr) == 3

    before_evt = ActionStateBefore.from_json(arr[0])
    assert before_evt.data.action_point_ids == {ap1_id} or before_evt.data.action_point_ids == {ap2_id}

    ps_evt = PackageState.from_json(arr[1])
    assert ps_evt.data.state == PackageState.Data.StateEnum.PAUSED

    before_evt2 = ActionStateBefore.from_json(arr[2])
    assert before_evt2.data.action_point_ids == {ap1_id} or before_evt2.data.action_point_ids == {ap2_id}

    assert before_evt2.data.action_point_ids != before_evt.data.action_point_ids

    # maybe it would be better to send command to stdin, but it's a bit complicated
    action.g.pause.clear()  # this would normally be done in _get_commands
    action.g.resume.set()

    # both threads should be finished
    th1.join(0.1)
    th2.join(0.1)

    assert not th1.is_alive()
    assert not th2.is_alive()
