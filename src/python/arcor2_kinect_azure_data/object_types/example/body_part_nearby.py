from time import sleep

from arcor2.data.common import Position
from arcor2_kinect_azure_data.object_types.example import BOX, POSE
from arcor2_kinect_azure_data.object_types.kinect_azure import BodyJoint, KinectAzure, UrlSettings

position = Position(0, 0, 1)  # +- 1m from camera
radius = 0.1  # 100mm
joint_id = BodyJoint.HAND_LEFT

settings = UrlSettings("localhost:5016")
k = KinectAzure("id", "foo", POSE, BOX, settings)

while True:
    print(f"{k.is_body_part_nearby(joint_id, radius, position)=}")
    sleep(0.2)
