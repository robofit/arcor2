import json
from dataclasses import dataclass

import pytest  # type: ignore

from arcor2.action import patch_object_actions
from arcor2.data.common import ActionMetadata, Parameter, StrEnum
from arcor2.object_types.abstract import Generic, GenericWithPose, Settings
from arcor2.object_types.utils import meta_from_def, object_actions, parse_def, settings_from_params
from arcor2.parameter_plugins import TYPE_TO_PLUGIN


class TestObject(GenericWithPose):
    """
    TestObject description
    """

    _ABSTRACT = False

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

    def action_2(self) -> bool:
        """
        Short description
        :return:
        """

    def action_3(self) -> None:
        pass

    action_1.__action__ = ActionMetadata(blocking=True)  # type: ignore
    action_2.__action__ = ActionMetadata()  # type: ignore
    # action_3 is missing its metadata


TestObject.CANCEL_MAPPING[TestObject.action_1.__name__] = TestObject.action_1_cancel.__name__

patch_object_actions(TestObject)


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
    assert not meta.settings


def test_object_actions() -> None:

    actions = object_actions(TestObject, parse_def(TestObject))
    assert len(actions) == 2

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

            assert act.meta == ActionMetadata()
            assert len(act.returns) == 1
            assert act.description == "Short description"
            assert not act.disabled
            assert act.origins is None
            assert not act.parameters
        else:
            pytest.fail(f"Unknown action: {act.name}.")


class MyEnum(StrEnum):

    OPT1: str = "opt1"
    OPT2: str = "opt2"
    OPT3: str = "opt3"


@dataclass
class NestedSettings(Settings):

    boolean: bool


@dataclass
class TestObjectSettings(Settings):

    string: str
    integer: int
    boolean: bool
    double: float
    enum: MyEnum
    nested_settings: NestedSettings


class TestObjectWithSettings(Generic):

    def __init__(self, obj_id: str, name: str, settings: TestObjectSettings) -> None:
        super(TestObjectWithSettings, self).__init__(obj_id, name, settings)


def test_settings() -> None:

    meta = meta_from_def(TestObjectWithSettings)
    assert len(meta.settings) == 6

    assert meta.settings[0].name == "string"
    assert not meta.settings[0].children
    assert meta.settings[0].type == TYPE_TO_PLUGIN[str].type_name()

    assert meta.settings[1].name == "integer"
    assert not meta.settings[1].children
    assert meta.settings[1].type == TYPE_TO_PLUGIN[int].type_name()

    assert meta.settings[2].name == "boolean"
    assert not meta.settings[2].children
    assert meta.settings[2].type == TYPE_TO_PLUGIN[bool].type_name()

    assert meta.settings[3].name == "double"
    assert not meta.settings[3].children
    assert meta.settings[3].type == TYPE_TO_PLUGIN[float].type_name()

    assert meta.settings[4].name == "enum"
    assert not meta.settings[4].children
    assert meta.settings[4].type == TYPE_TO_PLUGIN[StrEnum].type_name()

    assert meta.settings[5].name == "nested_settings"
    assert len(meta.settings[5].children) == 1
    assert meta.settings[5].type == "dataclass"  # TODO plugin for this?

    nested = meta.settings[5].children[0]

    assert nested.name == "boolean"
    assert not nested.children
    assert nested.type == TYPE_TO_PLUGIN[bool].type_name()


def test_settings_from_params() -> None:

    settings = settings_from_params(
        TestObjectWithSettings,
        [
            Parameter("string", "string", json.dumps("value")),
            Parameter("integer", "integer", json.dumps(1)),
            Parameter("boolean", "boolean", json.dumps(False)),
            Parameter("double", "double", json.dumps(1.0)),
            Parameter("enum", "enum", json.dumps(MyEnum.OPT1)),
            Parameter("nested_settings", "dataclass", NestedSettings(True).to_json())
        ],
        [
            Parameter("integer", "integer", json.dumps(2)),
            Parameter("double", "double", json.dumps(2.0))
        ]
    )

    assert isinstance(settings, TestObjectSettings)
