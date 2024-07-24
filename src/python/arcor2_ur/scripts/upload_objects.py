from arcor2.object_types.upload import Urdf, upload_def
from arcor2_ur import get_data
from arcor2_ur.object_types.ur5e import Ur5e


def main() -> None:
    upload_def(Ur5e, urdf=Urdf(get_data("urdf"), Ur5e.urdf_package_name))


if __name__ == "__main__":
    main()
