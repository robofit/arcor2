from typing import Any, List, Optional

from dataclasses_jsonschema import ValidationError
from typed_ast.ast3 import Call, Load, Name, Num

import arcor2.data.common
from arcor2.cached import CachedProject as CProject
from arcor2.cached import CachedScene as CScene
from arcor2.data.common import Orientation, Position, RelativePose
from arcor2.parameter_plugins.base import ImportTuple, ParameterPlugin, ParameterPluginException, TypesDict


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

    @classmethod
    def parameter_ast(
        cls, type_defs: TypesDict, scene: CScene, project: CProject, action_id: str, parameter_id: str
    ) -> Call:

        val = cls.parameter_value(type_defs, scene, project, action_id, parameter_id)

        return Call(
            func=Name(id=RelativePose.__name__, ctx=Load()),
            args=[
                Call(
                    func=Name(id=Position.__name__, ctx=Load()),
                    args=[Num(n=val.position.x), Num(n=val.position.y), Num(n=val.position.z)],
                    keywords=[],
                ),
                Call(
                    func=Name(id=Orientation.__name__, ctx=Load()),
                    args=[
                        Num(n=val.orientation.x),
                        Num(n=val.orientation.y),
                        Num(n=val.orientation.z),
                        Num(n=val.orientation.w),
                    ],
                    keywords=[],
                ),
            ],
            keywords=[],
        )

    @classmethod
    def need_to_be_imported(
        cls, type_defs: TypesDict, scene: CScene, project: CProject, action_id: str, parameter_id: str
    ) -> Optional[List[ImportTuple]]:

        mod = arcor2.data.common.__name__

        return [
            ImportTuple(mod, RelativePose.__name__),
            ImportTuple(mod, Position.__name__),
            ImportTuple(mod, Orientation.__name__),
        ]
