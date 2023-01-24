from time import sleep

from arcor2_kinect_azure_data.object_types.example import BOX, POSE
from arcor2_kinect_azure_data.object_types.kinect_azure import KinectAzure, UrlSettings

settings = UrlSettings("localhost:5016")
k = KinectAzure("id", "foo", POSE, BOX, settings)

while True:
    print(f"{k.get_people_count()=}")
    sleep(0.2)
