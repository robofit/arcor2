from arcor2.data.common import Project, Scene
from arcor2.parameter_plugins.base import TypesDict
from arcor2.parameter_plugins.integer import IntegerPlugin


class DoublePlugin(IntegerPlugin):

    @classmethod
    def type(cls):
        return float

    @classmethod
    def type_name(cls) -> str:
        return "double"

    @classmethod
    def value(cls, type_defs: TypesDict, scene: Scene, project: Project, action_id: str, parameter_id: str) -> float:
        return super(DoublePlugin, cls).value(type_defs, scene, project, action_id, parameter_id)
