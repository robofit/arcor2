#!/usr/bin/env python3

from arcor2.object_types.upload import Urdf, upload_def
from arcor2_fit_demo import get_data
from arcor2_fit_demo.object_types.abstract_dobot import AbstractDobot
from arcor2_fit_demo.object_types.dobot_m1 import DobotM1
from arcor2_fit_demo.object_types.dobot_magician import DobotMagician
from arcor2_fit_demo.object_types.kinect_azure import KinectAzure


def main() -> None:

    upload_def(AbstractDobot)
    upload_def(DobotMagician, urdf=Urdf(get_data("dobot-magician"), DobotMagician.urdf_package_name))
    upload_def(DobotM1, urdf=Urdf(get_data("dobot-m1"), DobotM1.urdf_package_name))
    upload_def(KinectAzure)  # TODO add its mesh


if __name__ == "__main__":
    main()
