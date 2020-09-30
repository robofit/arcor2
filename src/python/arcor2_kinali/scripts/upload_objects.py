#!/usr/bin/env python3

from arcor2.object_types.upload import upload_def
from arcor2_kinali.object_types.abstract_robot import AbstractRobot
from arcor2_kinali.object_types.abstract_simple import AbstractSimple
from arcor2_kinali.object_types.abstract_with_pose import AbstractWithPose
from arcor2_kinali.object_types.barcode import Barcode
from arcor2_kinali.object_types.interaction import Interaction
from arcor2_kinali.object_types.kinali_robot import KinaliRobot
from arcor2_kinali.object_types.search import Search
from arcor2_kinali.object_types.statistic import Statistic


def main() -> None:

    # abstract classes
    upload_def(AbstractRobot)
    upload_def(AbstractSimple)
    upload_def(AbstractWithPose)

    # concrete classes
    upload_def(Barcode)
    upload_def(Interaction)
    upload_def(KinaliRobot)
    upload_def(Search)
    upload_def(Statistic)


if __name__ == "__main__":
    main()
