import abc
from typing import FrozenSet
from arcor2 import DynamicParamDict, CancelDict
from arcor2.docstring import parse_docstring


class Service(metaclass=abc.ABCMeta):
    """
    A generic service.
    """

    DYNAMIC_PARAMS: DynamicParamDict = {}
    CANCEL_MAPPING: CancelDict = {}

    def __init__(self, configuration_id: str) -> None:
        self.configuration_id = configuration_id

    @property
    def id(self) -> str:
        return self.__class__.__name__

    @classmethod
    def description(cls) -> str:
        return parse_docstring(cls.__doc__)["short_description"]

    @staticmethod
    def get_configuration_ids() -> FrozenSet[str]:
        return frozenset()
