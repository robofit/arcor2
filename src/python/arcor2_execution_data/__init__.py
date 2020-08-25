from typing import Tuple, Type

from arcor2 import package_version
from arcor2.data.rpc.common import Request
from arcor2_execution_data import events, rpc

PORT = 6790

# RPCs that should be exposed to end clients (e.g. ARServer exposes those to AREditor).
exposed_rpcs: Tuple[Type[Request], ...] = (
    rpc.RunPackageRequest,
    rpc.StopPackageRequest,
    rpc.PausePackageRequest,
    rpc.ResumePackageRequest,
    rpc.PackageStateRequest,
    rpc.UploadPackageRequest,
    rpc.ListPackagesRequest,
    rpc.DeletePackageRequest,
    rpc.RenamePackageRequest,
)


def version() -> str:
    return package_version(__name__)


__all__ = [events.__name__, rpc.__name__, "PORT", version.__name__]
