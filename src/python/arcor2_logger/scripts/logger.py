import argparse
import os
import sys

import websockets
from aiologger.levels import LogLevel
from aiorun import run
from arcor2_logger import version
from arcor2_logger.object_types.logging_mixin import Level, LogMessage, Register
from dataclasses_jsonschema import ValidationError
from websockets.server import WebSocketServerProtocol as WsClient

from arcor2 import env
from arcor2.exceptions import Arcor2Exception
from arcor2.helpers import port_from_url
from arcor2.logging import get_aiologger

logger = get_aiologger("Logger")

logging_level = Level.from_string(os.getenv("ARCOR2_LOGGER_LEVEL", "info"))

# TODO maybe use the same machinery (arcor2/ws_server) for RPCs/Events as in ARServer/Execution?
# ...but for now this is much more simpler and just enough


async def handle_requests(websocket: WsClient, path: str) -> None:

    assert not sys.stdout.closed  # closed stdout was problem when creating and shutting down logger for each client

    try:
        data = await websocket.recv()
    except websockets.exceptions.ConnectionClosed:
        return

    assert isinstance(data, str)

    try:
        register = Register.from_json(data)
    except (ValidationError, Arcor2Exception) as e:
        logger.debug(f"Got invalid data. Expected '{Register.__name__}', received {data}. {str(e)}")
        return

    logger.info(f"{register.name} of type {register.type} just arrived to the party.")

    try:
        async for message in websocket:

            assert isinstance(message, str)

            try:
                lm = LogMessage.from_json(message)
            except (ValidationError, Arcor2Exception) as e:
                logger.debug(
                    f"Invalid data from {register.name}. Expected '{LogMessage.__name__}', received {message}. {str(e)}"
                )
                return

            msg = f"\033[1;36;49m{register.name}\033[0m {lm.message}"

            if lm.level < logging_level:
                continue

            if lm.level == Level.INFO:
                logger.info(msg)
            elif lm.level == Level.WARNING:
                logger.warning(msg)
            elif lm.level == Level.DEBUG:
                logger.debug(msg)
            elif lm.level == Level.ERROR:
                logger.error(msg)

    except websockets.exceptions.ConnectionClosed:
        logger.debug(f"Connection from {register.name} closed!")
        return

    logger.info(f"{register.name} of type {register.type} is leaving.")


async def aio_main() -> None:

    await websockets.server.serve(
        handle_requests, "localhost", port_from_url(os.getenv("ARCOR2_LOGGER_URL", "ws://0.0.0.0:8765"))
    )
    await logger.info(f"Logger service {version()} started. Logging level is {logging_level.name}.")


def main() -> None:
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "-d",
        "--debug",
        help="Set logging level to debug.",
        action="store_const",
        const=LogLevel.DEBUG,
        default=LogLevel.DEBUG if env.get_bool("ARCOR2_LOGGER_DEBUG") else LogLevel.INFO,
    )
    parser.add_argument("--version", action="version", version=version(), help="Shows version and exits.")
    parser.add_argument(
        "-a",
        "--asyncio_debug",
        help="Turn on asyncio debug mode.",
        action="store_const",
        const=True,
        default=env.get_bool("ARCOR2_LOGGER_ASYNCIO_DEBUG"),
    )

    args = parser.parse_args()
    logger.level = args.debug

    run(aio_main(), stop_on_unhandled_errors=True)


if __name__ == "__main__":
    main()
