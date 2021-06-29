from dataclasses import dataclass

from dataclasses_jsonschema import JsonSchemaMixin

from arcor2.data import common
from arcor2.data.events import Event


@dataclass
class ProjectChanged(Event):

    data: common.BareProject


@dataclass
class OpenProject(Event):
    @dataclass
    class Data(JsonSchemaMixin):
        scene: common.Scene
        project: common.Project

    data: Data


@dataclass
class ProjectSaved(Event):
    pass


@dataclass
class ProjectClosed(Event):
    pass


@dataclass
class ActionPointChanged(Event):
    data: common.BareActionPoint


@dataclass
class ActionChanged(Event):
    data: common.BareAction


@dataclass
class LogicItemChanged(Event):
    data: common.LogicItem


@dataclass
class ProjectParameterChanged(Event):
    data: common.ProjectParameter


@dataclass
class OrientationChanged(Event):
    data: common.NamedOrientation


@dataclass
class JointsChanged(Event):
    data: common.ProjectRobotJoints
