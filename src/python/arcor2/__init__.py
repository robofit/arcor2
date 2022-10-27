import pkgutil
import warnings
from typing import NamedTuple


class DynamicParamTuple(NamedTuple):

    method_name: str
    parent_parameters: set[str]


# key: name of parameter, value: name of method to call (to get set of strings), set of parent parameters
DynamicParamDict = dict[str, DynamicParamTuple]

# key: action, value: cancel method
CancelDict = dict[str, str]


if __debug__:
    warnings.filterwarnings("error", module="dataclasses_jsonschema")  # make warnings fatal because they are


def package_version(package: str, file: str = "VERSION") -> str:

    if res := pkgutil.get_data(package, file):
        return res.decode().strip()
    return "unknown"


def version() -> str:
    return package_version(__name__)
