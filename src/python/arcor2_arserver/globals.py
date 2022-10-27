import os
from collections import defaultdict
from typing import Any

from websockets.server import WebSocketServerProtocol as WsClient

from arcor2.data import events
from arcor2.object_types.abstract import Generic
from arcor2_arserver.lock import Lock
from arcor2_arserver.object_types.data import ObjectTypeDict, ObjTypeDict
from arcor2_arserver.user import Users
from arcor2_arserver_data.events.common import ShowMainScreen

VERBOSE: bool = False

PORT: int = int(os.getenv("ARCOR2_ARSERVER_PORT", 6789))

MAIN_SCREEN: None | ShowMainScreen.Data = ShowMainScreen.Data(ShowMainScreen.Data.WhatEnum.ScenesList)

OBJECT_TYPES: ObjectTypeDict = ObjTypeDict()

SCENE_OBJECT_INSTANCES: dict[str, Generic] = {}

RUNNING_ACTION: None | str = None  # ID of an action that is being executed during project editing
RUNNING_ACTION_PARAMS: None | list[Any] = None

PACKAGE_STATE = events.PackageState.Data()
PACKAGE_INFO: None | events.PackageInfo.Data = None

# there might be some long-running action being executed when ui connects, so let's them know
ACTION_STATE_BEFORE: None | events.ActionStateBefore.Data = None

TEMPORARY_PACKAGE: bool = False

RegisteredUiDict = defaultdict[str, set[WsClient]]

ROBOT_JOINTS_REGISTERED_UIS: RegisteredUiDict = defaultdict(lambda: set())  # robot, UIs
ROBOT_EEF_REGISTERED_UIS: RegisteredUiDict = defaultdict(lambda: set())  # robot, UIs

OBJECTS_WITH_UPDATED_POSE: set[str] = set()

LOCK: Lock = Lock(OBJECT_TYPES)

USERS: Users = Users()

PREV_RESULTS: dict[str, tuple[Any] | Any] = {}


def remove_prev_result(action_id: str) -> None:

    try:
        del PREV_RESULTS[action_id]
    except KeyError:
        pass
