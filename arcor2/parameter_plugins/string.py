from arcor2.data.common import Project, Scene
from arcor2.parameter_plugins.base import ParameterPlugin, TypesDict


class StringPlugin(ParameterPlugin):

    @classmethod
    def type(cls):
        return str

    @classmethod
    def type_name(cls) -> str:
        return "string"

    @classmethod
    def value(cls, type_defs: TypesDict, scene: Scene, project: Project, action_id: str, parameter_id: str) -> str:
        return super(StringPlugin, cls).value(type_defs, scene, project, action_id, parameter_id)
