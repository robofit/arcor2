import os

from arcor2 import package_version
from arcor2.data import events as arcor2_events
from arcor2.data.rpc.common import RPC, Version
from arcor2_execution_data import events, rpc
from arcor2_runtime.events import RobotEef, RobotJoints

URL = os.getenv("ARCOR2_EXECUTION_URL", "ws://0.0.0.0:6790")

# RPCs that should be exposed to end clients (e.g. ARServer exposes those to AREditor).
EXPOSED_RPCS: tuple[type[RPC], ...] = (
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

RPCS: tuple[type[RPC], ...] = EXPOSED_RPCS + (Version,)

EVENTS: tuple[type[arcor2_events.Event], ...] = (
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
