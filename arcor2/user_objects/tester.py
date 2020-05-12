from typing import List
import time

from arcor2.object_types import Generic
from arcor2.action import action
from arcor2.data.common import ActionMetadata


class Tester(Generic):
    """
    A generic tester
    """

    def __init__(self, *args, **kwargs):
        super(Tester, self).__init__(*args, **kwargs)
        self._cancel: bool = False
        self._param1: str = ""

    @action
    def run_test(self, seq: List[float], seq_id: List[str], eqp_res: List[bool]) -> List[bool]:
        return [bool(seq), bool(seq_id), bool(eqp_res)]

    @action
    def long_running_action(self) -> None:
        for _ in range(60):
            time.sleep(1)
            if self._cancel:
                self._cancel = False
                break

    @action
    def long_running_action_with_params(self, param1: str) -> None:
        self._param1 = param1
        for _ in range(60):
            time.sleep(1)
            if self._cancel:
                self._cancel = False
                break

    def simple_cancel(self) -> None:
        self._cancel = True

    def cancel_with_param(self, param1: str) -> None:
        assert param1 == self._param1
        self._cancel = True

    run_test.__action__ = ActionMetadata(blocking=True)
    long_running_action.__action__ = ActionMetadata(blocking=True)
    long_running_action_with_params.__action__ = ActionMetadata(blocking=True)


Tester.CANCEL_MAPPING[Tester.long_running_action.__name__] = Tester.simple_cancel.__name__
Tester.CANCEL_MAPPING[Tester.long_running_action_with_params.__name__] = Tester.cancel_with_param.__name__
