from arcor2_yumi import get_data
from arcor2_yumi.object_types.yumi import YuMi

from arcor2.object_types.upload import Urdf, upload_def


def main() -> None:

    upload_def(YuMi, urdf=Urdf(get_data("yumi"), YuMi.urdf_package_name))


if __name__ == "__main__":
    main()
