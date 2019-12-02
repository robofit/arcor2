from typing import Dict, Set, Tuple
import warnings

# key: name of parameter, value: name of method to call (to get set of strings), set of parent parameters
DynamicParamDict = Dict[str, Tuple[str, Set[str]]]

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
