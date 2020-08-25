from dataclasses import dataclass, field
from typing import Optional

from dataclasses_jsonschema import JsonSchemaMixin

from arcor2.data import common
from arcor2.data.events import Event, wo_suffix


@dataclass
class OpenSceneData(JsonSchemaMixin):

    scene: common.Scene


@dataclass
class OpenScene(Event):

    data: Optional[OpenSceneData] = None
    event: str = field(default=wo_suffix(__qualname__), init=False)  # type: ignore  # noqa: F821


@dataclass
class SceneChanged(Event):

    data: Optional[common.BareScene] = None
    event: str = field(default=wo_suffix(__qualname__), init=False)  # type: ignore  # noqa: F821


@dataclass
class SceneSaved(Event):

    event: str = field(default=wo_suffix(__qualname__), init=False)  # type: ignore  # noqa: F821


@dataclass
class SceneClosed(Event):

    event: str = field(default=wo_suffix(__qualname__), init=False)  # type: ignore  # noqa: F821


@dataclass
class SceneObjectChanged(Event):

    data: Optional[common.SceneObject] = None
    event: str = field(default=wo_suffix(__qualname__), init=False)  # type: ignore  # noqa: F821
