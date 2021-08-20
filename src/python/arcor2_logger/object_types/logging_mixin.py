from __future__ import annotations

import abc
import concurrent.futures as cf
import logging
import os
from dataclasses import dataclass
from typing import Optional, Protocol

import websocket
from dataclasses_jsonschema import JsonSchemaMixin

from arcor2.data.common import IntEnum
from arcor2.exceptions import Arcor2Exception


class Level(IntEnum):
    INFO = logging.INFO
    WARNING = logging.WARNING
    ERROR = logging.ERROR
    DEBUG = logging.DEBUG

    @classmethod
    def from_string(cls, value: str) -> Level:

        if value == "info":
            return cls.INFO
        elif value == "warning":
            return cls.WARNING
        elif value == "error":
            return cls.ERROR
        elif value == "debug":
            return cls.DEBUG

        raise Arcor2Exception(f"Unknown value {value}.")


@dataclass
class Register(JsonSchemaMixin):
    id: str
    name: str
    type: str


@dataclass
class LogMessage(JsonSchemaMixin):

    message: str
    level: Level


class Logger:
    def __init__(self, obj: GenericProtocol) -> None:

        self._ws = websocket.WebSocket()
        self._ws.connect(os.getenv("ARCOR2_LOGGER_URL", "ws://0.0.0.0:8765"))
        self._executor = cf.ThreadPoolExecutor(max_workers=1)
        self._executor.submit(self._ws.send, Register(obj.id, obj.name, obj.__class__.__name__).to_json())
        self._last_task: Optional[cf.Future] = None

    def _log(self, message: str, level: Level) -> None:
        if not self._ws.connected:
            raise Arcor2Exception("Not connected to the Logger service.")
        msg = LogMessage(message, level).to_json()
        self._last_task = self._executor.submit(self._ws.send, msg)

    def info(self, message: str) -> None:
        self._log(message, Level.INFO)

    def warning(self, message: str) -> None:
        self._log(message, Level.WARNING)

    def error(self, message: str) -> None:
        self._log(message, Level.ERROR)

    def __del__(self) -> None:
        self.close()

    def close(self) -> None:

        if self._last_task:
            try:
                cf.wait([self._last_task], 1.0)
            except cf.TimeoutError:
                pass
        self._ws.close()


class GenericProtocol(Protocol):
    @property
    def id(self) -> str:
        ...

    @property
    def name(self) -> str:
        ...


class LoggingMixin(metaclass=abc.ABCMeta):
    """Provides logging capabilities to ObjectTypes.

    Calls to all log_ methods are non-blocking.
    """

    def get_logger(self: GenericProtocol) -> Logger:
        return Logger(self)
