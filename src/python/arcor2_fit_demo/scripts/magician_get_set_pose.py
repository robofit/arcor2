import copy
import sys

from arcor2.data.common import Orientation, Pose, Position
from arcor2_fit_demo.object_types.abstract_dobot import DobotSettings
from arcor2_fit_demo.object_types.dobot_magician import DobotMagician


def main() -> None:

    dm = DobotMagician(
        "id", "name", Pose(Position(1, -1, -3), Orientation(0, 0, 0.707, 0.707)), DobotSettings("/dev/ttyUSB0")
    )
    orig_pose = dm.get_end_effector_pose("default")

    val = float(sys.argv[1])

    updated_pose = copy.deepcopy(orig_pose)
    updated_pose.position.x += val

    dm.move_to_pose("", updated_pose, 1.0)

    new_pose = dm.get_end_effector_pose("default")

    print(new_pose.position.x - orig_pose.position.x - val)


if __name__ == "__main__":
    main()
