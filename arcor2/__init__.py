from typing import Dict, Set, Tuple
import warnings
import pkgutil

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


def version() -> str:
    res = pkgutil.get_data(__name__, 'VERSION')
    if not res:
        return "unknown"
    return res.decode().strip()
