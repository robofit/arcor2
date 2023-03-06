import copy

from arcor2.data.common import Pose
from arcor2.exceptions import Arcor2Exception
from arcor2_yumi.object_types.yumi import YuMi, YumiSettings


def main() -> None:
    yumi = YuMi("", "", Pose(), YumiSettings("192.168.104.107"))

    try:
        yumi._left.reset_home()
        yumi._right.reset_home()

        pose_l = yumi.get_end_effector_pose("", "left")
        pose_r = yumi.get_end_effector_pose("", "right")

        pose_l_2 = copy.deepcopy(pose_l)
        pose_r_2 = copy.deepcopy(pose_r)

        pose_l_2.position.x += 0.25
        pose_r_2.position.x += 0.25

        pose_l_3 = copy.deepcopy(pose_l_2)
        pose_r_3 = copy.deepcopy(pose_r_2)

        pose_l_3.position.z += 0.1
        pose_r_3.position.z += 0.1

        try:
            while True:
                yumi.move_both_arms(pose_l_2, pose_r_2)
                yumi.move_both_arms(pose_l_3, pose_r_3)
                yumi.move_both_arms(pose_l_2, pose_r_2)
                yumi.move_both_arms(pose_l, pose_r)
        except KeyboardInterrupt:
            pass

    except Arcor2Exception as e:
        print(e)

    yumi.cleanup()


if __name__ == "__main__":
    main()
