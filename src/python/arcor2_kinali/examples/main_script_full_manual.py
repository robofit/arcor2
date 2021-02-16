#!/usr/bin/env python3

"""This is an example of the main script without usage of Resources class."""

# within an execution package, imports of ObjectTypes should be relative, e.g.:
# from object_types.aubo import Aubo
from arcor2 import rest
from arcor2.action import patch_object_actions
from arcor2.clients import scene_service
from arcor2.data.common import Joint, Pose, ProjectRobotJoints, uid
from arcor2.data.object_type import Box
from arcor2_kinali.object_types.abstract_robot import Settings as RobotSettings
from arcor2_kinali.object_types.abstract_simple import Settings as SimpleSettings
from arcor2_kinali.object_types.abstract_with_pose import Settings
from arcor2_kinali.object_types.aubo import Aubo, MoveTypeEnum
from arcor2_kinali.object_types.barcode import Barcode
from arcor2_kinali.object_types.ict import Ict
from arcor2_kinali.object_types.interaction import Interaction, NotificationLevelEnum
from arcor2_kinali.object_types.search import LogLevel, Search, SearchEngineParameters, SearchLogLevel
from arcor2_kinali.object_types.statistic import Statistic


def main() -> None:

    # robots
    aubo = Aubo(uid(), "Whatever", Pose(), RobotSettings("http://127.0.0.1:13000", "aubo"))
    simatic = Aubo(uid(), "Whatever", Pose(), RobotSettings("http://127.0.0.1:13001", "simatic"))

    # objects with pose, with 'System' and 'Configurations' controllers
    barcode = Barcode(uid(), "Whatever", Pose(), settings=Settings("http://127.0.0.1:14000", "simulator"))
    search = Search(uid(), "Whatever", Pose(), settings=Settings("http://127.0.0.1:12000", "simulator"))
    ict = Ict(uid(), "Whatever", Pose(), settings=Settings("http://127.0.0.1:19000", "simulator"))

    # objects without pose, without 'System' and 'Configurations' controllers
    interaction = Interaction(uid(), "Whatever", SimpleSettings("http://127.0.0.1:17000"))
    statistic = Statistic(uid(), "Whatever", SimpleSettings("http://127.0.0.1:16000"))

    # Add @action decorator to all actions of each object using patch_object_actions.
    # It has to be called exactly once for each type!
    # Certain functions of Execution unit (as e.g. pausing script execution) would not work without this step.
    # Note: in a generated script, this is done within the Resources context manager.
    # Side effect: a lot of JSON data will be printed out to the console when running the script manually.
    patch_object_actions(Aubo)
    patch_object_actions(Barcode)
    patch_object_actions(Search)
    patch_object_actions(Ict)
    patch_object_actions(Interaction)
    patch_object_actions(Statistic)

    scene_service.delete_all_collisions()
    scene_service.upsert_collision(Box("box_id", 0.1, 0.1, 0.1), Pose())
    scene_service.start()  # this is normally done by auto-generated Resources class

    aubo.move("suction", Pose(), MoveTypeEnum.SIMPLE, safe=False)
    simatic.set_joints(ProjectRobotJoints("", "", "", [Joint("x", 0), Joint("y", 0)]), MoveTypeEnum.SIMPLE)
    barcode.scan()
    search.set_search_parameters(SearchEngineParameters(search_log_level=SearchLogLevel(LogLevel.DEBUG)))
    search.grab_image()
    interaction.add_notification("Test", NotificationLevelEnum.INFO)

    try:
        statistic.get_groups()
    except rest.RestHttpException as e:
        # service returned error code
        print(f"The error code is {e.error_code}.")
    except rest.RestException as e:
        # request totally failed (timeout, connection error, etc)
        print(str(e))

    if ict.ready():
        test = ict.test("OK")
        print(test)

    scene_service.stop()  # this is normally done by auto-generated Resources class


if __name__ == "__main__":
    main()
