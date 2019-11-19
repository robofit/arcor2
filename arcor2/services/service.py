import abc
from typing import Set


class Service(metaclass=abc.ABCMeta):

    __DESCRIPTION__ = "A generic service."

    def __init__(self, configuration_id: str) -> None:
        self.configuration_id = configuration_id

    @staticmethod
    def get_configuration_ids() -> Set[str]:
        return set()
