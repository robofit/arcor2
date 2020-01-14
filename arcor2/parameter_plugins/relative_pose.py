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
            if isinstance(param.value, str):  # TODO support for str is only temporary, value should be dict!
                return RelativePose.from_json(param.value)
            elif isinstance(param.value, dict):
                return RelativePose.from_dict(param.value)
            else:
                raise ParameterPluginException("Invalid type of parameter value!")
        except ValidationError as e:
            raise ParameterPluginException(e)
