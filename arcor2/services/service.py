import abc
from typing import Set, Dict, Tuple, Callable


class Service(metaclass=abc.ABCMeta):

    __DESCRIPTION__ = "A generic service."

    def __init__(self, configuration_id: str) -> None:
        self.configuration_id = configuration_id

        # TODO this should be also defined for objects
        # TODO callable should return Set[??]
        self.params: Dict[str, Tuple[Callable, Set[str]]] = {}

    @staticmethod
    def get_configuration_ids() -> Set[str]:
        return set()
