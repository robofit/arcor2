import os

from arcor2.exceptions import Arcor2Exception


class Arcor2EnvException(Arcor2Exception):
    pass


def get_bool(variable_name: str, default: bool = False) -> bool:
    return os.getenv(variable_name, str(default)).lower() in ("true", "1")


def get_int(variable_name: str, default: None | int = None) -> int:

    val = os.getenv(variable_name, default)

    if val is None:
        raise Arcor2EnvException(f"Variable {variable_name} is not set.")

    try:
        return int(val)
    except ValueError:
        raise Arcor2EnvException(f"Variable {variable_name} has invalid value: {val}.")


def get_float(variable_name: str, default: None | float = None) -> float:

    val = os.getenv(variable_name, default)

    if val is None:
        raise Arcor2EnvException(f"Variable {variable_name} is not set.")

    try:
        return float(val)
    except ValueError:
        raise Arcor2EnvException(f"Variable {variable_name} has invalid value: {val}.")
