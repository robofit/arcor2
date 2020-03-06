from dataclasses_jsonschema import ValidationError


from arcor2.data.common import Project, Pose, Scene
from arcor2.parameter_plugins.base import ParameterPlugin, ParameterPluginException, TypesDict


class RelativePose(Pose):
    pass


class RelativePosePlugin(ParameterPlugin):

    @classmethod
    def type(cls):
        return RelativePose

    @classmethod
    def value(cls, type_defs: TypesDict, scene: Scene, project: Project, action_id: str, parameter_id: str) ->\
            RelativePose:

        param = project.action(action_id).parameter(parameter_id)

        try:
            return RelativePose.from_json(param.value)
        except ValidationError as e:
            raise ParameterPluginException(e)

    @classmethod
    def value_to_json(cls, value: RelativePose) -> str:
        return value.to_json()
