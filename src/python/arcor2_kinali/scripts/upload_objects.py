#!/usr/bin/env python3

from arcor2.object_types.upload import upload_def
from arcor2_kinali.object_types.barcode import Barcode
from arcor2_kinali.object_types.interaction import Interaction
from arcor2_kinali.object_types.kinali_abstract_object import KinaliAbstractObject
from arcor2_kinali.object_types.kinali_abstract_robot import KinaliAbstractRobot
from arcor2_kinali.object_types.kinali_robot import KinaliRobot
from arcor2_kinali.object_types.kinali_simple_object import KinaliSimpleObject
from arcor2_kinali.object_types.search import Search
from arcor2_kinali.object_types.statistic import Statistic


def main() -> None:

    # abstract classes
    upload_def(KinaliSimpleObject)
    upload_def(KinaliAbstractObject)
    upload_def(KinaliAbstractRobot)

    # concrete classes
    upload_def(Barcode)
    upload_def(Interaction)
    upload_def(KinaliRobot)
    upload_def(Search)
    upload_def(Statistic)


if __name__ == "__main__":
    main()
