from arcor2.data.common import ActionMetadata
from arcor2.object_types.abstract import Generic


class ParamToReturn(Generic):

    _ABSTRACT = False

    def bool_param(self, param: bool) -> bool:
        return param

    def int_param(self, param: int) -> int:
        return param

    def double_param(self, param: float) -> float:
        return param

    bool_param.__action__ = ActionMetadata(blocking=True)  # type: ignore
    int_param.__action__ = ActionMetadata(blocking=True)  # type: ignore
    double_param.__action__ = ActionMetadata(blocking=True)  # type: ignore
