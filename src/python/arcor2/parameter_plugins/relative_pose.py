from typing import Any

from dataclasses_jsonschema import ValidationError

from arcor2.cached import CachedProject as CProject
from arcor2.cached import CachedScene as CScene
from arcor2.data.common import Pose
from arcor2.parameter_plugins.base import ParameterPlugin, ParameterPluginException, TypesDict


class RelativePose(Pose):  # TODO why it is defined here and not in arcor2.data.common?
    pass


class RelativePosePlugin(ParameterPlugin):
    @classmethod
    def type(cls) -> Any:
        return RelativePose

    @classmethod
    def parameter_value(
        cls, type_defs: TypesDict, scene: CScene, project: CProject, action_id: str, parameter_id: str
    ) -> RelativePose:

        try:
            return RelativePose.from_json(project.action(action_id).parameter(parameter_id).value)
        except ValidationError as e:
            raise ParameterPluginException(e)

    @classmethod
    def value_to_json(cls, value: RelativePose) -> str:
        return value.to_json()
