#!/usr/bin/env python3
# -*- coding: utf-8 -*-


import asyncio
from typing import Dict, Set, Union, TYPE_CHECKING, Optional
from websockets.server import WebSocketServerProtocol
from aiologger import Logger  # type: ignore
from aiologger.levels import LogLevel  # type: ignore

from arcor2 import helpers as hlp
from arcor2.data.common import Scene, Project, Pose
from arcor2.data.object_type import ObjectActionsDict, ObjectTypeMetaDict
from arcor2.data.services import ServiceTypeMetaDict
from arcor2.data.robot import RobotMeta
from arcor2.data import rpc
from arcor2.object_types import Generic
from arcor2.services import Service
from arcor2.parameter_plugins.base import TypesDict

logger = Logger.with_default_handlers(name='server', formatter=hlp.aiologger_formatter(), level=LogLevel.DEBUG)

SCENE: Union[Scene, None] = None
PROJECT: Union[Project, None] = None

INTERFACES: Set[WebSocketServerProtocol] = set()

if TYPE_CHECKING:
    ReqQueue = asyncio.Queue[rpc.common.Request]
    RespQueue = asyncio.Queue[rpc.common.Response]
else:
    ReqQueue = asyncio.Queue
    RespQueue = asyncio.Queue

MANAGER_RPC_REQUEST_QUEUE: ReqQueue = ReqQueue()
MANAGER_RPC_RESPONSES: Dict[int, RespQueue] = {}

OBJECT_TYPES: ObjectTypeMetaDict = {}
SERVICE_TYPES: ServiceTypeMetaDict = {}
ROBOT_META: Dict[str, RobotMeta] = {}
TYPE_DEF_DICT: TypesDict = {}

# TODO merge it into one dict?
SCENE_OBJECT_INSTANCES: Dict[str, Generic] = {}
SERVICES_INSTANCES: Dict[str, Service] = {}

ACTIONS: ObjectActionsDict = {}  # used for actions of both object_types / services

FOCUS_OBJECT: Dict[str, Dict[int, Pose]] = {}  # object_id / idx, pose
FOCUS_OBJECT_ROBOT: Dict[str, rpc.common.RobotArg] = {}  # key: object_id


RUNNING_ACTION: Optional[str] = None
