#!/usr/bin/env python3

"""This is an example of the main script without usage of Resources class."""

from arcor2.clients import scene_service
from arcor2.data.common import Joint, Pose, ProjectRobotJoints, uid
from arcor2.data.object_type import Box
from arcor2_kinali.object_types.abstract_robot import Settings as RobotSettings
from arcor2_kinali.object_types.abstract_simple import Settings as SimpleSettings
from arcor2_kinali.object_types.abstract_with_pose import Settings
from arcor2_kinali.object_types.barcode import Barcode
from arcor2_kinali.object_types.interaction import Interaction, NotificationLevelEnum
from arcor2_kinali.object_types.kinali_robot import KinaliRobot, MoveTypeEnum
from arcor2_kinali.object_types.search import LogLevel, Search, SearchEngineParameters, SearchLogLevel
from arcor2_kinali.object_types.statistic import Statistic


def main() -> None:

    # robots
    aubo = KinaliRobot(uid(), "Whatever", Pose(), RobotSettings("http://127.0.0.1:13000", "aubo"))
    simatic = KinaliRobot(uid(), "Whatever", Pose(), RobotSettings("http://127.0.0.1:13001", "simatic"))

    # objects with pose, with 'System' and 'Configurations' controllers
    barcode = Barcode(uid(), "Whatever", Pose(), settings=Settings("http://127.0.0.1:14000", "simulator"))
    search = Search(uid(), "Whatever", Pose(), settings=Settings("http://127.0.0.1:12000", "simulator"))

    # objects without pose, without 'System' and 'Configurations' controllers
    interaction = Interaction(uid(), "Whatever", SimpleSettings("http://127.0.0.1:17000"))
    statistic = Statistic(uid(), "Whatever", SimpleSettings("http://127.0.0.1:16000"))

    scene_service.delete_all_collisions()
    scene_service.upsert_collision(Box("box_id", 0.1, 0.1, 0.1), Pose())
    scene_service.start()  # this is normally done by auto-generated Resources class

    aubo.move("suction", Pose(), MoveTypeEnum.SIMPLE, safe=False)
    simatic.set_joints(ProjectRobotJoints("", "", "", [Joint("x", 0), Joint("y", 0)]), MoveTypeEnum.SIMPLE)
    barcode.scan()
    search.set_search_parameters(SearchEngineParameters(search_log_level=SearchLogLevel(LogLevel.DEBUG)))
    search.grab_image()
    interaction.add_notification("Test", NotificationLevelEnum.INFO)
    statistic.get_groups()

    scene_service.stop()  # this is normally done by auto-generated Resources class


if __name__ == "__main__":
    main()
