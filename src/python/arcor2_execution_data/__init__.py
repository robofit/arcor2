import os
from typing import Tuple, Type

from arcor2_runtime.events import RobotEef, RobotJoints

from arcor2 import package_version
from arcor2.data import events as arcor2_events
from arcor2.data.rpc.common import RPC, Version
from arcor2_execution_data import events, rpc

URL = os.getenv("ARCOR2_EXECUTION_URL", "ws://0.0.0.0:6790")

# RPCs that should be exposed to end clients (e.g. ARServer exposes those to AREditor).
EXPOSED_RPCS: Tuple[Type[RPC], ...] = (
    rpc.RunPackage,
    rpc.StopPackage,
    rpc.PausePackage,
    rpc.ResumePackage,
    rpc.UploadPackage,
    rpc.ListPackages,
    rpc.DeletePackage,
    rpc.RenamePackage,
    rpc.StepAction,
)

RPCS: Tuple[Type[RPC], ...] = EXPOSED_RPCS + (Version,)

EVENTS: Tuple[Type[arcor2_events.Event], ...] = (
    events.PackageChanged,
    arcor2_events.PackageState,
    arcor2_events.PackageInfo,
    arcor2_events.ProjectException,
    arcor2_events.ActionStateBefore,
    arcor2_events.ActionStateAfter,
    RobotJoints,
    RobotEef,
)


def version() -> str:
    return package_version(__name__)


__all__ = [events.__name__, rpc.__name__, version.__name__]
