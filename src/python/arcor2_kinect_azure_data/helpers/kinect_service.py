import os
import time

from arcor2.exceptions import Arcor2Exception
from arcor2.rest import Method, RestException, call

URL = os.getenv("ARCOR2_KINECT_AZURE_URL", "http://0.0.0.0:5016")


class KinectServiceException(Arcor2Exception):
    pass


def wait_for(timeout: float = 10.0) -> None:
    start_time = time.monotonic()
    while time.monotonic() < start_time + timeout:
        try:
            call(Method.GET, f"{URL}/")
            return
        except RestException:
            pass
        time.sleep(1.0)

    raise KinectServiceException("Failed to contact Kinect service.")
