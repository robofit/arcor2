#!/usr/bin/env python3

from arcor2.data.object_type import Mesh
from arcor2.object_types.upload import Urdf, upload_def, upload_whatever
from arcor2_fit_demo import get_data
from arcor2_fit_demo.object_types.abstract_dobot import AbstractDobot
from arcor2_fit_demo.object_types.conveyor_belt import ConveyorBelt
from arcor2_fit_demo.object_types.dobot_m1 import DobotM1
from arcor2_fit_demo.object_types.dobot_magician import DobotMagician
from arcor2_fit_demo.object_types.fit_common_mixin import FitCommonMixin
from arcor2_fit_demo.object_types.kinect_azure import KinectAzure


def main() -> None:

    upload_def(AbstractDobot)
    upload_def(DobotMagician, urdf=Urdf(get_data("dobot-magician"), DobotMagician.urdf_package_name))
    upload_def(DobotM1, urdf=Urdf(get_data("dobot-m1"), DobotM1.urdf_package_name))
    upload_def(
        KinectAzure,
        Mesh(KinectAzure.__name__, KinectAzure.mesh_filename),
        file_to_upload=get_data(KinectAzure.mesh_filename),
    )
    upload_def(
        ConveyorBelt,
        Mesh(ConveyorBelt.__name__, ConveyorBelt.mesh_filename),
        file_to_upload=get_data(ConveyorBelt.mesh_filename),
    )
    upload_whatever(FitCommonMixin)


if __name__ == "__main__":
    main()
