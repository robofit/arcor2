import json
from threading import Lock
from typing import NamedTuple, Optional

import numpy as np
import pyk4a
from PIL import Image
from pyk4a import Config, ImageFormat, K4AException, PyK4A, PyK4ACapture

from arcor2.data.camera import CameraParameters
from arcor2.exceptions import Arcor2Exception


class KinectAzureException(Arcor2Exception):
    pass


class ColorAndDepthImage(NamedTuple):

    color: Image.Image
    depth: Image.Image


class KinectAzure:
    def __init__(self) -> None:

        self._lock = Lock()

        self._k4a = PyK4A(
            Config(
                color_resolution=pyk4a.ColorResolution.RES_1080P,
                depth_mode=pyk4a.DepthMode.NFOV_UNBINNED,
                synchronized_images_only=True,
                color_format=ImageFormat.COLOR_BGRA32,
            )
        )
        self._k4a.start()
        self._k4a.exposure_mode_auto = True

        c = json.loads(self._k4a.calibration_raw)

        # https://github.com/microsoft/Azure-Kinect-Sensor-SDK/blob/develop/examples/opencv_compatibility/main.cpp
        # https://github.com/etiennedub/pyk4a/issues/69#issuecomment-698756626

        # order of parameters in JSON hopefully corresponds to order of parameters in this struct
        # https://microsoft.github.io/Azure-Kinect-Sensor-SDK/master/structk4a__calibration__intrinsic__parameters__t_1_1__param.html

        # for mode related offsets see this
        # https://github.com/microsoft/Azure-Kinect-Sensor-SDK/blob/90f77529f5ad19efd1e8f155a240c329e3bcbbdf/src/transformation/mode_specific_calibration.c#L95

        # "CALIBRATION_LensDistortionModelBrownConrady"

        img = self.color_image()

        # no need to handle depth camera parameters as we will always provide transformed depth image
        self.color_camera_params: Optional[CameraParameters] = None

        try:
            for camera in c["CalibrationInformation"]["Cameras"]:

                params = camera["Intrinsics"]["ModelParameters"]

                cx = params[0]
                cy = params[1]

                fx = params[2]
                fy = params[3]

                k1 = params[4]
                k2 = params[5]
                k3 = params[6]
                k4 = params[7]
                k5 = params[8]
                k6 = params[9]

                p2 = params[12]
                p1 = params[13]

                cp = CameraParameters(fx, fy, cx, cy, [k1, k2, p1, p2, k3, k4, k5, k6])

                if camera["Location"] == "CALIBRATION_CameraLocationPV0":

                    h = img.width / 4 * 3

                    # un-normalize values
                    cp.cx *= img.width
                    cp.cy *= h
                    cp.fx *= img.width
                    cp.fy *= h

                    assert self.color_camera_params is None

                    # apply crop offset
                    cp.cy -= (img.width / 4 * 3 - img.width / 16 * 9) / 2
                    self.color_camera_params = cp

                    break

        except (KeyError, IndexError) as e:
            raise KinectAzureException("Failed to parse calibration.") from e

        if self.color_camera_params is None:
            raise KinectAzureException("Failed to get camera calibration.")

    def _bgra_to_rgba(self, arr: np.ndarray) -> None:

        arr[:, :, [0, 1, 2, 3]] = arr[:, :, [2, 1, 0, 3]]

    def _capture(self) -> PyK4ACapture:

        with self._lock:

            try:
                return self._k4a.get_capture(timeout=1000)
            except K4AException as e:
                raise KinectAzureException("Failed to get capture.") from e

    def color_image(self) -> Image.Image:

        capture = self._capture()

        if capture.color is None:
            raise KinectAzureException("Color image not available.")

        self._bgra_to_rgba(capture.color)
        return Image.fromarray(capture.color, mode="RGBA")

    def _depth_image(self) -> np.ndarray:

        capture = self._capture()

        if capture.transformed_depth is None:
            raise KinectAzureException("Depth image not available.")

        return capture.transformed_depth

    def depth_image(self, averaged_frames: int = 1) -> Image.Image:

        img = self._depth_image()
        array = img.astype(np.float32)

        for _ in range(averaged_frames):
            array += self._depth_image().astype(np.float32)

        return Image.fromarray((array / averaged_frames).astype(img.dtype))

    def sync_images(self) -> ColorAndDepthImage:

        capture = self._capture()

        if not capture.color or not capture.depth:
            raise KinectAzureException("Color/depth image not available.")

        self._bgra_to_rgba(capture.color)
        return ColorAndDepthImage(Image.fromarray(capture.color), Image.fromarray(capture.transformed_depth))

    def cleanup(self) -> None:
        self._k4a.stop()
