import io
from typing import Optional

import pytest
from arcor2_runtime.action import ACTION_NAME_ID_MAPPING_ATTR, AP_ID_ATTR, patch_object_actions

from arcor2.data.common import ActionMetadata, Orientation, Pose, Position
from arcor2.data.events import ActionStateAfter, ActionStateBefore
from arcor2.exceptions import Arcor2Exception
from arcor2.object_types.abstract import Generic


def test_patch_object_actions(monkeypatch, capsys) -> None:
    class MyObject(Generic):
        def action(self, pose: Pose, *, an: Optional[str] = None) -> None:
            pass

        action.__action__ = ActionMetadata()  # type: ignore

    # @action tries to read from stdin
    sio = io.StringIO()
    sio.fileno = lambda: 0  # type: ignore  # fake whatever fileno
    monkeypatch.setattr("sys.stdin", sio)

    obj_id = "123"
    pose = Pose(Position(0, 0, 0), Orientation(1, 0, 0, 0))
    setattr(pose, AP_ID_ATTR, "pose")  # set pose id (simulate pose declaration in scene json)

    my_obj = MyObject(obj_id, "")

    my_obj.action(pose)
    out_before, _ = capsys.readouterr()
    assert not out_before

    patch_object_actions(MyObject)
    setattr(MyObject, ACTION_NAME_ID_MAPPING_ATTR, {"name": "id"})  # this simulates what patch_with_action_mapping does

    my_obj.action(pose, an="name")
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

    with pytest.raises(Arcor2Exception):
        my_obj.action(pose, an="unknown_action_name")


def test_patch_object_actions_without_mapping(monkeypatch, capsys) -> None:
    class MyObject(Generic):
        def action(self, pose: Pose, *, an: Optional[str] = None) -> None:
            pass

        action.__action__ = ActionMetadata()  # type: ignore

    # @action tries to read from stdin
    sio = io.StringIO()
    sio.fileno = lambda: 0  # type: ignore  # fake whatever fileno
    monkeypatch.setattr("sys.stdin", sio)

    obj_id = "123"
    pose = Pose(Position(0, 0, 0), Orientation(1, 0, 0, 0))
    setattr(pose, AP_ID_ATTR, "pose")  # set pose id (simulate pose declaration in scene json)

    my_obj = MyObject(obj_id, "")
    patch_object_actions(MyObject)  # no mapping given

    my_obj.action(pose)  # this should be ok
    out_after, _ = capsys.readouterr()

    assert out_after

    arr = out_after.strip().split("\n")
    assert len(arr) == 1

    before_evt = ActionStateBefore.from_json(arr[0])

    assert before_evt.data.action_point_ids is not None
    assert "pose" in before_evt.data.action_point_ids

    my_obj.action(pose, an="whatever")  # why would anyone do this... but should be also ok
    out_after, _ = capsys.readouterr()
    assert out_after


def test_composite_action(monkeypatch, capsys) -> None:
    class MyObject(Generic):
        def inner_inner_action(self, *, an: Optional[str] = None) -> None:
            pass

        def inner_action(self, *, an: Optional[str] = None) -> None:
            self.inner_inner_action()

        def inner_action_2(self, *, an: Optional[str] = None) -> None:
            pass

        def action(self, *, an: Optional[str] = None) -> None:
            self.inner_action()
            self.inner_action_2()

        def action_wo_flag(self, *, an: Optional[str] = None) -> None:
            self.inner_action()
            self.inner_action_2()

        def action_with_inner_name_spec(self, *, an: Optional[str] = None) -> None:
            self.inner_action(an="whatever")

        inner_inner_action.__action__ = ActionMetadata()  # type: ignore
        inner_action.__action__ = ActionMetadata(composite=True)  # type: ignore
        inner_action_2.__action__ = ActionMetadata()  # type: ignore
        action.__action__ = ActionMetadata(composite=True)  # type: ignore
        action_wo_flag.__action__ = ActionMetadata()  # type: ignore
        action_with_inner_name_spec.__action__ = ActionMetadata()  # type: ignore

    # @action tries to read from stdin
    sio = io.StringIO()
    sio.fileno = lambda: 0  # type: ignore  # fake whatever fileno
    monkeypatch.setattr("sys.stdin", sio)

    obj_id = "123"

    my_obj = MyObject(obj_id, "")

    my_obj.action()
    out_before, _ = capsys.readouterr()
    assert not out_before

    patch_object_actions(MyObject)
    setattr(MyObject, ACTION_NAME_ID_MAPPING_ATTR, {"name": "id"})  # this simulates what patch_with_action_mapping does

    my_obj.action(an="name")
    out_after, _ = capsys.readouterr()

    arr = out_after.strip().split("\n")
    assert len(arr) == 5

    before_evt = ActionStateBefore.from_json(arr[0])
    after_evt = ActionStateAfter.from_json(arr[4])

    assert before_evt.data.action_id == "id"
    assert after_evt.data.action_id == "id"

    with pytest.raises(Arcor2Exception, match="Mapping from action name to id provided, but action name not set."):
        my_obj.action()

    invalid_an = "unknown_action_name"
    with pytest.raises(Arcor2Exception, match=f"Mapping from action name to id is missing key {invalid_an}."):
        my_obj.action(an=invalid_an)

    with pytest.raises(
        Arcor2Exception, match=f"Outer action {my_obj.action_wo_flag.__name__}/id not flagged as composite."
    ):
        my_obj.action_wo_flag(an="name")

    with pytest.raises(Arcor2Exception, match="Inner actions should not have name specified."):
        my_obj.action_with_inner_name_spec(an="name")
