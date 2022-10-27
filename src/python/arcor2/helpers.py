import asyncio
import builtins
import importlib
import keyword
import os
import socket
import sys
from concurrent import futures
from contextlib import closing
from threading import Lock
from typing import Any, Callable, TypeVar

import humps
from packaging.version import Version, parse

from arcor2.exceptions import Arcor2Exception


class ImportClsException(Arcor2Exception):
    pass


class TypeDefException(Arcor2Exception):
    pass


def is_valid_identifier(value: str) -> None:
    """
    Identifier (e.g. object id) will be used as variable name in the script - it should
    not contain any special characters etc.
    :param value:
    :return:
    """

    if not value:
        raise Arcor2Exception("Empty string is not enough.")

    if not (value[0].isalpha() or value[0] == "_"):
        raise Arcor2Exception("It has to start with character or underscore.")

    for c in value[1:]:
        if c == " ":
            raise Arcor2Exception("Use underscore instead of space.")
        if not (c.isalnum() or c == "_"):
            raise Arcor2Exception(f"Character '{c}' can't be used.")

    assert value.isidentifier()

    if keyword.iskeyword(value) or value in builtins.__dict__.keys():
        raise Arcor2Exception("Reserved keyword.")


def is_valid_type(value: str) -> None:
    is_valid_identifier(value)


S = TypeVar("S")


async def run_in_executor(
    func: Callable[..., S],
    *args: Any,
    executor: None | futures.Executor = None,
    propagate: None | list[type[Exception]] = None,
) -> S:
    """Executes synchronous function in an executor. Catches all exceptions are
    re-raises them as Arcor2Exception.

    :param func:
    :param args:
    :param executor:
    :param propagate: Exceptions to propagate.
    :return:
    """

    # TODO user typing.ParamSpec instead of *args: Any (Python 3.10 or typing-extensions)
    # ...not supported by mypy at the moment, see https://github.com/python/mypy/issues/8645

    try:
        return await asyncio.get_event_loop().run_in_executor(executor, func, *args)
    except Arcor2Exception:
        raise
    except Exception as e:

        if propagate:
            for etp in propagate:
                if isinstance(e, etp):
                    raise

        # all code should raise exceptions based on Arcor2Exception so this is just a guard against a buggy code
        raise Arcor2Exception(f"Unhandled exception in {func.__name__}.") from e


T = TypeVar("T")


def save_and_import_type_def(source: str, type_name: str, output_type: type[T], path: str, module_name: str) -> type[T]:
    """Save source to a file in object_type_path directory.

    :param source:
    :param type_name:
    :param output_type:
    :param object_type_path:
    :return:
    """

    type_file = humps.depascalize(type_name)
    full_path = f"{os.path.join(path, module_name, type_file)}.py"

    with open(full_path, "w") as file:
        file.write(source)

    try:
        return import_type_def(type_name, output_type, path, module_name)
    except Arcor2Exception:
        os.remove(full_path)
        raise


def import_type_def(type_name: str, output_type: type[T], path: str, module_name: str) -> type[T]:
    """Save source to a file in object_type_path directory.

    :param source:
    :param type_name:
    :param output_type:
    :param object_type_path:
    :return:
    """

    if path not in sys.path:
        sys.path.append(path)

    type_file = humps.depascalize(type_name)

    importlib.invalidate_caches()  # otherwise import might fail randomly (not sure why exactly)

    try:
        module = importlib.import_module(f"{module_name}.{type_file}")

        # reload is necessary for cases when the module is already loaded
        module = importlib.reload(module)  # TODO does this really solve anything?

    except ImportError as e:
        raise ImportClsException(f"Failed to import '{module_name}.{type_file}'. {str(e).capitalize()}.") from e
    except Exception as e:
        raise ImportClsException(
            f"Error occurred when importing '{module_name}.{type_file}'. {str(e).capitalize()}."
        ) from e

    if not module.__file__:
        raise ImportClsException(f"Can't get file for '{module_name}.{type_file}'.")

    path_to_file = os.path.abspath(module.__file__)
    assert os.path.exists(path_to_file), f"Path {path_to_file} does not exist."

    try:
        cls = getattr(module, type_name)
    except AttributeError:
        raise ImportClsException(f"Class {type_name} not found in module '{module_name}'.")

    if not issubclass(cls, output_type):
        raise ImportClsException(f"{cls.__name__} is not subclass of {output_type.__name__}.")

    return cls


def check_compatibility(my_version: str, their_version: str) -> None:

    try:
        mv = parse(my_version)
        tv = parse(their_version)
    except ValueError as e:
        raise Arcor2Exception from e

    if not isinstance(mv, Version):
        raise Arcor2Exception(f"{my_version} is not a proper version.")

    if not isinstance(tv, Version):
        raise Arcor2Exception(f"{their_version} is not a proper version.")

    if mv.major != tv.major:
        raise Arcor2Exception("Different major version.")

    if mv.major == 0:
        if mv.minor != tv.minor:
            raise Arcor2Exception(f"Our version {my_version} is not compatible with {their_version}.")
    else:
        if mv.minor > tv.minor:
            raise Arcor2Exception(f"Our version {my_version} is outdated for {their_version}.")


class NonBlockingLock:
    """This lock can only be used as a context manager."""

    __slots__ = ("_lock",)

    def __init__(self) -> None:
        self._lock = Lock()

    def locked(self) -> bool:
        return self._lock.locked()

    def __enter__(self) -> None:
        if not self._lock.acquire(blocking=False):
            raise Arcor2Exception("Can't get the lock.")

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        self._lock.release()
        return None


def port_from_url(url: str) -> int:

    return int(url.strip().split(":")[-1])


def find_free_port() -> int:
    with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as s:
        s.bind(("localhost", 0))
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        return s.getsockname()[1]
