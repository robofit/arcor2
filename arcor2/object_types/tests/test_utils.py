import inspect

import horast

import pytest  # type: ignore

from arcor2.action import action
from arcor2.data.common import ActionMetadata
from arcor2.object_types.abstract import GenericWithPose
from arcor2.object_types.utils import meta_from_def, object_actions
from arcor2.parameter_plugins import TYPE_TO_PLUGIN


class TestObject(GenericWithPose):
    """
    TestObject description
    """

    @action
    def action_1(self, param1: str, param2: int, param3: bool = False) -> None:
        """
        Short description
        :param param1: str param
        :param param2: int param
        :param param3: bool param
        :return:
        """
        assert 0 <= param2 <= 100

    def action_1_cancel(self) -> None:
        pass

    @action
    def action_2(self) -> bool:
        """
        Short description
        :return:
        """

    @action
    def action_3(self) -> None:
        pass

    # action_4 is missing @action decorator
    def action_4(self) -> None:
        pass

    action_1.__action__ = ActionMetadata(blocking=True)  # type: ignore
    action_2.__action__ = ActionMetadata(free=True)  # type: ignore
    # action_3 is missing its metadata
    action_4.__action__ = ActionMetadata()  # type: ignore


TestObject.CANCEL_MAPPING[TestObject.action_1.__name__] = TestObject.action_1_cancel.__name__


def test_meta_from_def() -> None:

    meta = meta_from_def(TestObject)
    assert meta.type == TestObject.__name__
    assert meta.description == "TestObject description"
    assert not meta.disabled
    assert not meta.abstract
    assert not meta.needs_parent_type
    assert not meta.settings
    assert meta.object_model is None
    assert not meta.built_in
    assert meta.base == GenericWithPose.__name__
    assert meta.has_pose


def test_object_actions() -> None:

    source = inspect.getsource(TestObject)
    actions = object_actions(TYPE_TO_PLUGIN, TestObject, horast.parse(source))
    assert len(actions) == 3  # TODO object_actions can't check if method has decorator (yet)

    for act in actions.values():

        if act.name == TestObject.action_1.__name__:

            expected_meta = ActionMetadata(blocking=True)
            expected_meta.cancellable = True
            assert act.meta == expected_meta
            assert not act.returns
            assert act.description == "Short description"
            assert not act.disabled
            assert act.origins is None
            assert len(act.parameters) == 3

            for param in act.parameters:
                if param.name == "param1":
                    assert param.description == "str param"
                elif param.name == "param2":
                    assert param.description == "int param"
                elif param.name == "param3":
                    assert param.description == "bool param"
                else:
                    pytest.fail(f"Unknown parameter: {param.name} of action {act.name}.")

        elif act.name == TestObject.action_2.__name__:

            assert act.meta == ActionMetadata(free=True)
            assert len(act.returns) == 1
            assert act.description == "Short description"
            assert not act.disabled
            assert act.origins is None
            assert not act.parameters

        elif act.name == TestObject.action_4.__name__:
            # TODO should not be reported here (missing @action decorator)
            pass
        else:
            pytest.fail(f"Unknown action: {act.name}.")
