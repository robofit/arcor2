import asyncio
import importlib
import keyword
import logging
import os
import sys
import time
import traceback
from threading import Lock
from types import ModuleType
from typing import Any, Callable, Tuple, Type, TypeVar

import humps
from aiologger.formatters.base import Formatter  # type: ignore
from packaging.version import Version, parse

from arcor2.data.events import ProjectException
from arcor2.exceptions import Arcor2Exception

LOG_FORMAT = "%(name)s - %(levelname)-8s: %(message)s"


class ImportClsException(Arcor2Exception):
    pass


class TypeDefException(Arcor2Exception):
    pass


def aiologger_formatter() -> Formatter:

    return Formatter(LOG_FORMAT)


def logger_formatter() -> logging.Formatter:

    return logging.Formatter(LOG_FORMAT)


def import_cls(module_cls: str) -> Tuple[ModuleType, Type[Any]]:
    """Gets module and class based on string like 'module/Cls'.

    :param module_cls:
    :return:
    """

    try:
        module_name, cls_name = module_cls.split("/")
    except (IndexError, ValueError):
        raise ImportClsException("Invalid format.")

    try:
        module = importlib.import_module(module_name)
    except ModuleNotFoundError:
        raise ImportClsException(f"Module '{module_name}' not found.")

    try:
        cls = getattr(module, cls_name)
    except AttributeError:
        raise ImportClsException(f"Class {cls_name} not found in module '{module_name}'.")

    return module, cls


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


def format_stacktrace() -> str:
    parts = ["Traceback (most recent call last):\n"]
    parts.extend(traceback.format_stack(limit=25)[:-2])
    parts.extend(traceback.format_exception(*sys.exc_info())[1:])
    return "".join(parts)


def print_exception(e: Exception) -> None:

    if isinstance(e, Arcor2Exception):
        pee = ProjectException(ProjectException.Data(e.message, e.__class__.__name__, True))
    else:
        pee = ProjectException(ProjectException.Data(str(e), e.__class__.__name__))

    print(pee.to_json())
    sys.stdout.flush()

    with open("traceback-{}.txt".format(time.strftime("%Y%m%d-%H%M%S")), "w") as tb_file:
        tb_file.write(format_stacktrace())


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

    if path not in sys.path:
        sys.path.append(path)

    type_file = humps.depascalize(type_name)
    full_path = os.path.join(path, module_name, type_file)

    with open(f"{full_path}.py", "w") as file:
        file.write(source)

    try:
        module = importlib.import_module(f"{module_name}.{type_file}")
    except ModuleNotFoundError:
        raise ImportClsException(f"Module '{module_name}' not found.")

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
