from arcor2.data.common import Project, Scene
from arcor2.parameter_plugins.base import ParameterPlugin, TypesDict


class BooleanPlugin(ParameterPlugin):

    @classmethod
    def type(cls):
        return bool

    @classmethod
    def type_name(cls) -> str:
        return "boolean"

    @classmethod
    def value(cls, type_defs: TypesDict, scene: Scene, project: Project, action_id: str, parameter_id: str) -> bool:
        return cls.type()(super(BooleanPlugin, cls).value(type_defs, scene, project, action_id, parameter_id))
