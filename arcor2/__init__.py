from typing import Dict, Tuple, Callable, Set

DynamicParamDict = Dict[str, Tuple[Callable[..., Set[str]], Set[str]]]
