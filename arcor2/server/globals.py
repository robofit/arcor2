#!/usr/bin/env python3
# -*- coding: utf-8 -*-


import os
from collections import defaultdict
from typing import Any, DefaultDict, Dict, Optional, Set

from aiologger import Logger  # type: ignore
from aiologger.levels import LogLevel  # type: ignore

from websockets.server import WebSocketServerProtocol as WsClient

from arcor2 import helpers as hlp
from arcor2.cached import UpdateableCachedProject
from arcor2.data import events
from arcor2.data.common import ActionState, CurrentAction, PackageState, Scene
from arcor2.data.execution import PackageInfo
from arcor2.data.object_type import ObjectActionsDict, ObjectTypeMetaDict
from arcor2.data.robot import RobotMeta
from arcor2.data.services import ServiceTypeMetaDict
from arcor2.nodes.build import PORT as BUILD_PORT
from arcor2.nodes.execution import PORT as EXE_PORT
from arcor2.object_types import Generic
from arcor2.parameter_plugins.base import TypesDict
from arcor2.services.service import Service

logger = Logger.with_default_handlers(name='server', formatter=hlp.aiologger_formatter(), level=LogLevel.DEBUG)
VERBOSE: bool = False

MANAGER_URL = os.getenv("ARCOR2_EXECUTION_URL", f"ws://0.0.0.0:{EXE_PORT}")
BUILDER_URL = os.getenv("ARCOR2_BUILDER_URL", f"http://0.0.0.0:{BUILD_PORT}")

PORT: int = int(os.getenv("ARCOR2_SERVER_PORT", 6789))

SCENE: Optional[Scene] = None
PROJECT: Optional[UpdateableCachedProject] = None
MAIN_SCREEN: Optional[events.ShowMainScreenData] = \
    events.ShowMainScreenData(events.ShowMainScreenData.WhatEnum.ScenesList)

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
RUNNING_ACTION_PARAMS: Optional[Dict[str, Any]] = None

PACKAGE_STATE = PackageState()
PACKAGE_INFO: Optional[PackageInfo] = None
ACTION_STATE: Optional[ActionState] = None
CURRENT_ACTION: Optional[CurrentAction] = None
TEMPORARY_PACKAGE: bool = False

RegisteredUiDict = DefaultDict[str, Set[WsClient]]

ROBOT_JOINTS_REGISTERED_UIS: RegisteredUiDict = defaultdict(lambda: set())  # robot, UIs
ROBOT_EEF_REGISTERED_UIS: RegisteredUiDict = defaultdict(lambda: set())  # robot, UIs
