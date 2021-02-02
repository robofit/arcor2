import os
from collections import defaultdict
from typing import Any, DefaultDict, Dict, List, Optional, Set

from websockets.server import WebSocketServerProtocol as WsClient

from arcor2.cached import UpdateableCachedProject, UpdateableCachedScene
from arcor2.data import events
from arcor2.logging import get_aiologger
from arcor2.object_types.abstract import Generic
from arcor2_arserver.object_types.data import ObjectTypeDict
from arcor2_arserver_data.events.common import ShowMainScreen

logger = get_aiologger("ARServer")
VERBOSE: bool = False

PORT: int = int(os.getenv("ARCOR2_SERVER_PORT", 6789))

SCENE: Optional[UpdateableCachedScene] = None
PROJECT: Optional[UpdateableCachedProject] = None

MAIN_SCREEN: Optional[ShowMainScreen.Data] = ShowMainScreen.Data(ShowMainScreen.Data.WhatEnum.ScenesList)

INTERFACES: Set[WsClient] = set()

OBJECT_TYPES: ObjectTypeDict = {}

SCENE_OBJECT_INSTANCES: Dict[str, Generic] = {}

RUNNING_ACTION: Optional[str] = None  # ID of an action that is being executed during project editing
RUNNING_ACTION_PARAMS: Optional[List[Any]] = None

PACKAGE_STATE = events.PackageState.Data()
PACKAGE_INFO: Optional[events.PackageInfo.Data] = None

# there might be some long-running action being executed when ui connects, so let's them know
ACTION_STATE_BEFORE: Optional[events.ActionStateBefore.Data] = None

TEMPORARY_PACKAGE: bool = False

RegisteredUiDict = DefaultDict[str, Set[WsClient]]

ROBOT_JOINTS_REGISTERED_UIS: RegisteredUiDict = defaultdict(lambda: set())  # robot, UIs
ROBOT_EEF_REGISTERED_UIS: RegisteredUiDict = defaultdict(lambda: set())  # robot, UIs

OBJECTS_WITH_UPDATED_POSE: Set[str] = set()
