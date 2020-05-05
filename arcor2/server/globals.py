#!/usr/bin/env python3
# -*- coding: utf-8 -*-


from typing import Dict, Set, Union, Optional, DefaultDict
import os
from collections import defaultdict

from websockets.server import WebSocketServerProtocol as WsClient
from aiologger import Logger  # type: ignore
from aiologger.levels import LogLevel  # type: ignore

from arcor2 import helpers as hlp
from arcor2.data.common import Scene, Project, PackageState, PackageInfo, ActionState, CurrentAction
from arcor2.data.object_type import ObjectActionsDict, ObjectTypeMetaDict
from arcor2.data import events
from arcor2.data.services import ServiceTypeMetaDict
from arcor2.data.robot import RobotMeta
from arcor2.object_types import Generic
from arcor2.services import Service
from arcor2.parameter_plugins.base import TypesDict
from arcor2 import nodes

logger = Logger.with_default_handlers(name='server', formatter=hlp.aiologger_formatter(), level=LogLevel.DEBUG)
VERBOSE: bool = False

MANAGER_URL = os.getenv("ARCOR2_EXECUTION_URL", f"ws://0.0.0.0:{nodes.execution.PORT}")
BUILDER_URL = os.getenv("ARCOR2_BUILDER_URL", f"http://0.0.0.0:{nodes.build.PORT}")

PORT: int = int(os.getenv("ARCOR2_SERVER_PORT", 6789))

SCENE: Union[Scene, None] = None
PROJECT: Union[Project, None] = None

INTERFACES: Set[WsClient] = set()

OBJECT_TYPES: ObjectTypeMetaDict = {}
SERVICE_TYPES: ServiceTypeMetaDict = {}
ROBOT_META: Dict[str, RobotMeta] = {}
TYPE_DEF_DICT: TypesDict = {}

# TODO merge it into one dict?
SCENE_OBJECT_INSTANCES: Dict[str, Generic] = {}
SERVICES_INSTANCES: Dict[str, Service] = {}

ACTIONS: ObjectActionsDict = {}  # used for actions of both object_types / services

RUNNING_ACTION: Optional[str] = None  # ID of an action that is being executed during project editing

PACKAGE_STATE = PackageState()
PACKAGE_INFO: Optional[PackageInfo] = None
ACTION_STATE: Optional[ActionState] = None
CURRENT_ACTION: Optional[CurrentAction] = None
SCENE_COLLISIONS: Optional[events.SceneCollisionsData] = None

RegisteredUiDict = DefaultDict[str, Set[WsClient]]

ROBOT_JOINTS_REGISTERED_UIS: RegisteredUiDict = defaultdict(lambda: set())  # robot, UIs
ROBOT_EEF_REGISTERED_UIS: RegisteredUiDict = defaultdict(lambda: set())  # robot, UIs
