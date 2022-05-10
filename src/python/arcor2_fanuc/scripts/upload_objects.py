from arcor2_fanuc import get_data
from arcor2_fanuc.object_types.fake_fanuc import FakeFanuc
from arcor2_fanuc.object_types.fanuc import Fanuc
from arcor2_fanuc.object_types.fanuc_lrmate200id7l import FanucLRMate200id7L

from arcor2.object_types.upload import Urdf, upload_def


def main() -> None:
    upload_def(Fanuc)
    upload_def(FanucLRMate200id7L, urdf=Urdf(get_data("urdf"), FanucLRMate200id7L.urdf_package_name))
    upload_def(FakeFanuc, urdf=Urdf(get_data("urdf"), FakeFanuc.urdf_package_name))


if __name__ == "__main__":
    main()
