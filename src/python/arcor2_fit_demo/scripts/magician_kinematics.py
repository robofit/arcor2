import math

import quaternion

from arcor2.data.common import Pose
from arcor2_fit_demo.object_types.abstract_dobot import DobotSettings
from arcor2_fit_demo.object_types.dobot_magician import DobotMagician


def main() -> None:

    dm = DobotMagician("id", "name", Pose(), DobotSettings("/dev/ttyUSB0"))

    joints = dm.robot_joints()
    pose = dm.get_end_effector_pose("default")
    print(pose)
    print(joints)
    print(quaternion.as_euler_angles(pose.orientation.as_quaternion()))

    print("--- Forward Kinematics -----------------------------")

    fk_pose = dm.forward_kinematics("", joints)

    dx = pose.position.x - fk_pose.position.x
    dy = pose.position.y - fk_pose.position.y
    dz = pose.position.z - fk_pose.position.z

    print("Position error: {:+.09f}".format(math.sqrt(dx ** 2 + dy ** 2 + dz ** 2)))

    print("dx: {:+.06f}".format(dx))
    print("dy: {:+.06f}".format(dy))
    print("dz: {:+.06f}".format(dz))

    print(fk_pose.orientation)

    print("--- Inverse Kinematics -----------------------------")

    ik_joints = dm.inverse_kinematics("", pose)

    assert len(ik_joints) == len(joints)

    for idx, (joint, ik_joint) in enumerate(zip(joints, ik_joints)):
        print("j{}: {:+.06f}".format(idx + 1, joint.value - ik_joint.value))


if __name__ == "__main__":
    main()
