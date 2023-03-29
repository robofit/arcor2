from .fanuc import Fanuc  # noqa:ABS101


class FanucLRMate200id7L(Fanuc):
    _ABSTRACT = False
    urdf_package_name = "fanuc_lrmate200id7l.zip"
