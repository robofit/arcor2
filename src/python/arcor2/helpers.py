import asyncio
import importlib
import keyword
import os
import socket
import sys
from contextlib import closing
from threading import Lock
from typing import Callable, Type, TypeVar

import humps
from packaging.version import Version, parse

from arcor2.exceptions import Arcor2Exception


class ImportClsException(Arcor2Exception):
    pass


class TypeDefException(Arcor2Exception):
    pass


def is_valid_identifier(value: str) -> bool:
    """
    Identifier (e.g. object id) will be used as variable name in the script - it should be in snake_case,
    not containing any special characters etc.
    :param value:
    :return:
    """

    return value.isidentifier() and not keyword.iskeyword(value) and humps.is_snakecase(value)


def is_valid_type(value: str) -> bool:
    """
    Value will be used as object type name - it should be in CamelCase,
    not containing any special characters etc.
    :param value:
    :return:
    """

    return value.isidentifier() and not keyword.iskeyword(value) and humps.is_pascalcase(value)


S = TypeVar("S")


async def run_in_executor(func: Callable[..., S], *args) -> S:
    return await asyncio.get_event_loop().run_in_executor(None, func, *args)


T = TypeVar("T")


def save_and_import_type_def(source: str, type_name: str, output_type: Type[T], path: str, module_name: str) -> Type[T]:
    """Save source to a file in object_type_path directory.

    :param source:
    :param type_name:
    :param output_type:
    :param object_type_path:
    :return:
    """

    type_file = humps.depascalize(type_name)
    full_path = os.path.join(path, module_name, type_file)

    with open(f"{full_path}.py", "w") as file:
        file.write(source)

    return import_type_def(type_name, output_type, path, module_name)


def import_type_def(type_name: str, output_type: Type[T], path: str, module_name: str) -> Type[T]:
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

    try:
        module = importlib.import_module(f"{module_name}.{type_file}")
    except ModuleNotFoundError:
        raise ImportClsException(f"Module '{module_name}' not found.")

    # this is necessary for cases when the module is already loaded
    importlib.reload(module)

    try:
        cls = getattr(module, type_name)
    except AttributeError:
        raise ImportClsException(f"Class {type_name} not found in module '{module_name}'.")

    if not issubclass(cls, output_type):
        raise ImportClsException("Not a required type.")

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

    def __init__(self):
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
