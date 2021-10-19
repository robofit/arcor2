import asyncio

from websockets.server import WebSocketServerProtocol

from arcor2 import ws_server
from arcor2.data import events
from arcor2_arserver import globals as glob
from arcor2_arserver import logger


async def broadcast_event(event: events.Event) -> None:

    logger.debug(event)

    if glob.USERS.interfaces:
        message = event.to_json()
        await asyncio.gather(*[ws_server.send_json_to_client(intf, message) for intf in glob.USERS.interfaces])


async def event(interface: WebSocketServerProtocol, event: events.Event) -> None:
    await ws_server.send_json_to_client(interface, event.to_json())
