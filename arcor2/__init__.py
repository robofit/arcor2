from typing import Dict, Tuple, Callable, Set
import warnings

DynamicParamDict = Dict[str, Tuple[Callable[..., Set[str]], Set[str]]]

warnings.filterwarnings(
    action='ignore',
    category=UserWarning,
    module='quaternion'
)

warnings.filterwarnings(
    action='ignore',
    category=UserWarning,
    module='dataclasses_jsonschema',
    message="Unable to create schema for 'Any'"
)
