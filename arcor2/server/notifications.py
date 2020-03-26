import asyncio
from typing import Optional, Callable

from websockets.server import WebSocketServerProtocol

from arcor2.data import events
from arcor2.server import globals as glob


def scene_event() -> events.SceneChangedEvent:

    return events.SceneChangedEvent(glob.SCENE)


def project_event() -> events.ProjectChangedEvent:

    return events.ProjectChangedEvent(glob.PROJECT)

async def notify(event: events.Event, exclude_ui=None):

    if (exclude_ui is None and glob.INTERFACES) or (exclude_ui and len(glob.INTERFACES) > 1):
        message = event.to_json()
        await asyncio.wait([intf.send(message) for intf in glob.INTERFACES if intf != exclude_ui])


async def _notify(interface, msg_source: Callable[[], events.Event]):

    await notify(msg_source(), interface)


async def notify_scene_change_to_others(interface: Optional[WebSocketServerProtocol] = None) -> None:

    await _notify(interface, scene_event)


async def notify_project_change_to_others(interface=None) -> None:

    await _notify(interface, project_event)


async def notify_scene(interface) -> None:
    message = scene_event().to_json()
    await asyncio.wait([interface.send(message)])


async def notify_project(interface) -> None:
    message = project_event().to_json()
    await asyncio.wait([interface.send(message)])