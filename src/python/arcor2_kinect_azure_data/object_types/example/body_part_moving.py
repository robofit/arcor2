from time import sleep

from arcor2.data.common import Position
from arcor2_kinect_azure_data.object_types.example import BOX, POSE
from arcor2_kinect_azure_data.object_types.kinect_azure import BodyJoint, KinectAzure, UrlSettings

joint_id = BodyJoint.HAND_LEFT
direction = Position(1, 0, 0)
speed = 0.05
deviation = 0.2

settings = UrlSettings("localhost:5016")
k = KinectAzure("id", "foo", POSE, BOX, settings)

while True:
    print(f"{k.is_body_part_moving(joint_id, speed, direction, deviation)=}")
    sleep(0.2)
