from arcor2.data.common import ActionMetadata
from arcor2.object_types.abstract import Generic


class ParamToReturn(Generic):

    _ABSTRACT = False

    def bool_param(self, param: bool, *, an: None | str = None) -> bool:
        return param

    def int_param(self, param: int, *, an: None | str = None) -> int:
        return param

    def double_param(self, param: float, *, an: None | str = None) -> float:
        return param

    bool_param.__action__ = ActionMetadata()  # type: ignore
    int_param.__action__ = ActionMetadata()  # type: ignore
    double_param.__action__ = ActionMetadata()  # type: ignore
