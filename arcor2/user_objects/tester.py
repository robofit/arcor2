from typing import List

from arcor2.object_types import Generic
from arcor2.action import action
from arcor2.data.common import ActionMetadata


class Tester(Generic):
    """
    A generic tester
    """

    @action
    def run_test(self, seq: List[float], seq_id: List[str], eqp_res: List[bool]) -> List[bool]:
        return [bool(seq), bool(seq_id), bool(eqp_res)]

    run_test.__action__ = ActionMetadata(blocking=True)
