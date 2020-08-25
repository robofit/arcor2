import asyncio
from typing import Optional

from websockets.server import WebSocketServerProtocol

from arcor2 import ws_server
from arcor2.data import events
from arcor2_arserver import globals as glob


async def broadcast_event(event: events.Event, exclude_ui: Optional[WebSocketServerProtocol] = None) -> None:

    if (exclude_ui is None and glob.INTERFACES) or (exclude_ui and len(glob.INTERFACES) > 1):
        message = event.to_json()
        await asyncio.gather(
            *[ws_server.send_json_to_client(intf, message) for intf in glob.INTERFACES if intf != exclude_ui]
        )


async def event(interface: WebSocketServerProtocol, event: events.Event) -> None:
    await ws_server.send_json_to_client(interface, event.to_json())
