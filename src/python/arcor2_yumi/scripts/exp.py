import copy

from arcor2_yumi.object_types.yumi import YuMi, YumiSettings

from arcor2.data.common import Pose


def main() -> None:

    yumi = YuMi("", "", Pose(), YumiSettings("192.168.104.107"))

    left_joints = yumi.robot_joints(arm_id="left")
    right_joints = yumi.robot_joints(arm_id="right")

    print(yumi.forward_kinematics("", left_joints, "left"))
    print(yumi.forward_kinematics("", right_joints, "right"))

    pose_l = yumi.get_end_effector_pose("", "left")
    pose_r = yumi.get_end_effector_pose("", "right")

    print(yumi.inverse_kinematics("", pose_l, None, False, arm_id="left"))
    print(yumi.inverse_kinematics("", pose_r, None, False, arm_id="right"))

    pose_l_2 = copy.deepcopy(pose_l)
    pose_r_2 = copy.deepcopy(pose_r)

    pose_l_2.position.z += 0.01
    pose_r_2.position.z += 0.01

    while True:
        yumi.move_to_pose("", pose_l, 0.5, arm_id="left")
        yumi.move_to_pose("", pose_l_2, 0.5, arm_id="left")
        yumi.move_to_pose("", pose_r, 0.5, arm_id="right")
        yumi.move_to_pose("", pose_r_2, 0.5, arm_id="right")


if __name__ == "__main__":
    main()
