#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""This is an example of the main script without usage of Resources class.

So far, it is necessary to initialize Scene service (0.1.0) separately - for instance using Swagger UI.
"""

from arcor2 import rest
from arcor2.clients import scene_service
from arcor2.data.common import Joint, Pose, ProjectRobotJoints, uid
from arcor2.data.object_type import Box
from arcor2_kinali.object_types.barcode import Barcode
from arcor2_kinali.object_types.interaction import Interaction, NotificationLevelEnum
from arcor2_kinali.object_types.kinali_abstract_object import KinaliSettings
from arcor2_kinali.object_types.kinali_abstract_robot import KinaliRobotSettings
from arcor2_kinali.object_types.kinali_robot import KinaliRobot, MoveTypeEnum
from arcor2_kinali.object_types.search import LogLevel, Search, SearchEngineParameters, SearchLogLevel
from arcor2_kinali.object_types.statistic import Statistic


def main() -> None:

    rest.TIMEOUT = (3.05, 8 * 60 * 60)  # workaround for long timeouts for Interaction service / Robot

    aubo = KinaliRobot(uid(), "Whatever", Pose(), KinaliRobotSettings("http://127.0.0.1:13000", "aubo"))
    simatic = KinaliRobot(uid(), "Whatever", Pose(), KinaliRobotSettings("http://127.0.0.1:13001", "simatic"))
    barcode = Barcode(uid(), "Whatever", KinaliSettings("http://127.0.0.1:14000", "simulator"))
    search = Search(uid(), "Whatever", KinaliSettings("http://127.0.0.1:12000", "simulator"))
    interaction = Interaction(uid(), "Whatever", KinaliSettings("http://127.0.0.1:17000", "simulator"))
    statistic = Statistic(uid(), "Whatever", KinaliSettings("http://127.0.0.1:16000", "simulator"))

    scene_service.delete_all_collisions()
    scene_service.upsert_collision(Box("box_id", 0.1, 0.1, 0.1), Pose())

    aubo.move("suction", Pose(), MoveTypeEnum.AVOID_COLLISIONS)
    simatic.set_joints(ProjectRobotJoints("", "", "", [Joint("x", 0), Joint("y", 0)]), MoveTypeEnum.SIMPLE)
    barcode.scan("scanned_ir")
    search.set_search_parameters(SearchEngineParameters(search_log_level=SearchLogLevel(LogLevel.DEBUG)))
    search.grab_image()
    interaction.add_notification("Test", NotificationLevelEnum.INFO)
    statistic.get_groups()


if __name__ == "__main__":
    main()
