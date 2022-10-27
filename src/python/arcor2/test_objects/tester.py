import time

from arcor2.data.common import ActionMetadata
from arcor2.object_types.abstract import CollisionObject


class Tester(CollisionObject):
    """A generic tester."""

    _ABSTRACT = False

    def __init__(self, *args, **kwargs) -> None:
        super(Tester, self).__init__(*args, **kwargs)
        self._cancel: bool = False
        self._param1: str = ""

    def run_test(
        self, seq: list[float], seq_id: list[str], eqp_res: list[bool], *, an: None | str = None
    ) -> list[bool]:
        """Run test with many parameters.

        :param seq:
        :param seq_id:
        :param eqp_res:
        :return:
        """
        return [bool(seq), bool(seq_id), bool(eqp_res)]

    def long_running_action(self, *, an: None | str = None) -> None:
        """This runs for long time.

        :return:
        """
        for _ in range(60):
            time.sleep(1)
            if self._cancel:
                self._cancel = False
                break

    def long_running_action_with_params(self, param1: str, *, an: None | str = None) -> None:
        """Runs for long time.

        :param param1:
        :return:
        """
        self._param1 = param1
        for _ in range(60):
            time.sleep(1)
            if self._cancel:
                self._cancel = False
                break

    def simple_cancel(self, *, an: None | str = None) -> None:
        self._cancel = True

    def cancel_with_param(self, param1: str, *, an: None | str = None) -> None:
        assert param1 == self._param1
        self._cancel = True

    run_test.__action__ = ActionMetadata()  # type: ignore
    long_running_action.__action__ = ActionMetadata()  # type: ignore
    long_running_action_with_params.__action__ = ActionMetadata()  # type: ignore


Tester.CANCEL_MAPPING[Tester.long_running_action.__name__] = Tester.simple_cancel.__name__
Tester.CANCEL_MAPPING[Tester.long_running_action_with_params.__name__] = Tester.cancel_with_param.__name__
