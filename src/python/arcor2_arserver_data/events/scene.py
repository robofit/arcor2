from dataclasses import dataclass

from dataclasses_jsonschema import JsonSchemaMixin

from arcor2.data import common
from arcor2.data.events import Event


@dataclass
class OpenScene(Event):
    @dataclass
    class Data(JsonSchemaMixin):
        scene: common.Scene

    data: Data


@dataclass
class SceneChanged(Event):
    data: common.BareScene


@dataclass
class SceneSaved(Event):
    pass


@dataclass
class SceneClosed(Event):
    pass


@dataclass
class SceneObjectChanged(Event):
    data: common.SceneObject
