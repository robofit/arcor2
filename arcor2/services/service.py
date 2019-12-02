import abc
from typing import Set
from arcor2 import DynamicParamDict
from arcor2.docstring import parse_docstring


class Service(metaclass=abc.ABCMeta):
    """
    A generic service.
    """

    DYNAMIC_PARAMS: DynamicParamDict = {}

    def __init__(self, configuration_id: str) -> None:
        self.configuration_id = configuration_id

    @property
    def id(self) -> str:
        return self.__class__.__name__

    @classmethod
    def description(cls) -> str:
        return parse_docstring(cls.__doc__)["short_description"]

    @staticmethod
    def get_configuration_ids() -> Set[str]:
        return set()
