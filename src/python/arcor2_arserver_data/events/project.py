from dataclasses import dataclass, field
from typing import Optional

from dataclasses_jsonschema import JsonSchemaMixin

from arcor2.data import common
from arcor2.data.events import Event, wo_suffix


@dataclass
class ProjectChanged(Event):

    data: Optional[common.BareProject] = None
    event: str = field(default=wo_suffix(__qualname__), init=False)  # type: ignore  # noqa: F821


@dataclass
class OpenProjectData(JsonSchemaMixin):

    scene: common.Scene
    project: common.Project


@dataclass
class OpenProject(Event):

    data: Optional[OpenProjectData] = None
    event: str = field(default=wo_suffix(__qualname__), init=False)  # type: ignore  # noqa: F821


@dataclass
class ProjectSaved(Event):

    event: str = field(default=wo_suffix(__qualname__), init=False)  # type: ignore  # noqa: F821


@dataclass
class ProjectClosed(Event):

    event: str = field(default=wo_suffix(__qualname__), init=False)  # type: ignore  # noqa: F821


@dataclass
class ActionPointChanged(Event):

    data: Optional[common.BareActionPoint] = None
    event: str = field(default=wo_suffix(__qualname__), init=False)  # type: ignore  # noqa: F821


@dataclass
class ActionChanged(Event):

    data: Optional[common.BareAction] = None
    event: str = field(default=wo_suffix(__qualname__), init=False)  # type: ignore  # noqa: F821


@dataclass
class LogicItemChanged(Event):

    data: Optional[common.LogicItem] = None
    event: str = field(default=wo_suffix(__qualname__), init=False)  # type: ignore  # noqa: F821


@dataclass
class ProjectConstantChanged(Event):

    data: Optional[common.ProjectConstant] = None
    event: str = field(default=wo_suffix(__qualname__), init=False)  # type: ignore  # noqa: F821


@dataclass
class OrientationChanged(Event):

    data: Optional[common.NamedOrientation] = None
    event: str = field(default=wo_suffix(__qualname__), init=False)  # type: ignore  # noqa: F821


@dataclass
class JointsChanged(Event):

    data: Optional[common.ProjectRobotJoints] = None
    event: str = field(default=wo_suffix(__qualname__), init=False)  # type: ignore  # noqa: F821
