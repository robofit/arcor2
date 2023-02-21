from arcor2.data.common import ActionPoint, Position
from copy import deepcopy
from arcor2_runtime.resources import Resources

class ap1:

    def __init__(self, res: Resources):
        self._position = res.project.bare_action_point('acp_cac07ce859ee4637b8f5ac0c7c30a7dd').position

    @property
    def position(self) -> Position:
        return deepcopy(self._position)


class ActionPoints:

    def __init__(self, res: Resources):
        self.ap1 = ap1(res)
