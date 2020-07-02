import pkgutil
import warnings
from typing import Dict, NamedTuple, Set


class DynamicParamTuple(NamedTuple):

    method_name: str
    parent_parameters: Set[str]


# key: name of parameter, value: name of method to call (to get set of strings), set of parent parameters
DynamicParamDict = Dict[str, DynamicParamTuple]

# key: action, value: cancel method
CancelDict = Dict[str, str]

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


def _version(file: str) -> str:

    res = pkgutil.get_data(__name__, file)
    if not res:
        return "unknown"
    return res.decode().strip()


def version() -> str:
    return _version('VERSION')


def api_version() -> str:
    return _version('API_VERSION')
