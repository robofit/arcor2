from time import sleep

from arcor2.data.common import Position
from arcor2_kinect_azure_data.object_types.example import BOX, POSE
from arcor2_kinect_azure_data.object_types.kinect_azure import KinectAzure, UrlSettings

settings = UrlSettings("localhost:5016")
k = KinectAzure("id", "foo", POSE, BOX, settings)
position = Position(0, 0, 0.5)
threshold = 0.1  # 50mm radius

while True:
    print(f"{k.is_colliding(threshold=threshold, position=position)=}")
    sleep(0.2)
