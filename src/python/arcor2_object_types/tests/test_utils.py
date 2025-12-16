import json
from dataclasses import dataclass

from arcor2.data.common import Parameter, StrEnum
from arcor2_object_types.abstract import Generic, Settings
from arcor2_object_types.utils import settings_from_params


class MyEnum(StrEnum):
    OPT1 = "opt1"
    OPT2 = "opt2"
    OPT3 = "opt3"


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


def test_settings_from_params() -> None:
    settings = settings_from_params(
        TestObjectWithSettings,
        [
            Parameter("string", "string", json.dumps("value")),
            Parameter("integer", "integer", json.dumps(1)),
            Parameter("boolean", "boolean", json.dumps(False)),
            Parameter("double", "double", json.dumps(1.0)),
            Parameter("enum", "enum", json.dumps(MyEnum.OPT1)),
            Parameter("nested_settings", "dataclass", NestedSettings(True).to_json()),
        ],
        [Parameter("integer", "integer", json.dumps(2)), Parameter("double", "double", json.dumps(2.0))],
    )

    assert isinstance(settings, TestObjectSettings)
