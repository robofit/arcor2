#!/usr/bin/env python3

from arcor2.object_types.upload import Urdf, upload_def
from arcor2_kinali import get_data
from arcor2_kinali.object_types.abstract_robot import AbstractRobot
from arcor2_kinali.object_types.abstract_simple import AbstractSimple
from arcor2_kinali.object_types.abstract_with_pose import AbstractWithPose
from arcor2_kinali.object_types.aubo import Aubo
from arcor2_kinali.object_types.barcode import Barcode
from arcor2_kinali.object_types.ict import Ict
from arcor2_kinali.object_types.interaction import Interaction
from arcor2_kinali.object_types.search import Search
from arcor2_kinali.object_types.simatic import Simatic
from arcor2_kinali.object_types.statistic import Statistic


def main() -> None:

    # abstract classes
    upload_def(AbstractRobot)
    upload_def(AbstractSimple)
    upload_def(AbstractWithPose)

    # concrete classes
    upload_def(Barcode)
    upload_def(Interaction)
    upload_def(Aubo, urdf=Urdf(get_data("aubo"), Aubo.urdf_package_name))
    upload_def(Simatic)
    upload_def(Search)
    upload_def(Statistic)
    upload_def(Ict)


if __name__ == "__main__":
    main()
