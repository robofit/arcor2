import json
import logging
import threading
import time
from collections import deque
from threading import Lock
from typing import Generator, NamedTuple

import cv2
import numpy as np
import pyk4a
from PIL import Image
from pyk4a import Config, ImageFormat, K4AException, PyK4A, PyK4ACapture

from arcor2.data.camera import CameraParameters
from arcor2.data.common import Orientation, Pose, Position
from arcor2.exceptions import Arcor2Exception
from arcor2.logging import get_logger
from arcor2.transformations import make_pose_abs, make_pose_rel
from arcor2_kinect_azure import ARCOR2_KINECT_AZURE_LOG_LEVEL
from arcor2_kinect_azure.kinect.common import parse_skeleton


class KinectAzureException(Arcor2Exception):
    pass


class ColorAndDepthImage(NamedTuple):
    color: Image.Image
    depth: Image.Image


class KinectAzure:
    CAPTURE_BUFFER_CAP = 30

    def __init__(self) -> None:
        self._lock = Lock()

        self._config = Config(
            color_resolution=pyk4a.ColorResolution.RES_1536P,
            camera_fps=pyk4a.FPS.FPS_30,
            depth_mode=pyk4a.DepthMode.NFOV_UNBINNED,
            synchronized_images_only=True,
            color_format=ImageFormat.COLOR_BGRA32,
        )
        self._k4a = PyK4A(self._config)
        self._k4a.start()
        self._k4a.exposure_mode_auto = True

        self._camera_pose = Pose(Position(), Orientation())

        self._kinect_logger = get_logger("kinect_logger", ARCOR2_KINECT_AZURE_LOG_LEVEL)
        # Keep 1 second of images
        self._capture_buffer: deque[PyK4ACapture] = deque(maxlen=self.CAPTURE_BUFFER_CAP)
        self._running_capture_thread: bool = False
        self._capture_thread: threading.Thread | None = None

        if self.color_camera_params is None:
            raise KinectAzureException("Failed to get camera calibration.")

    def get_camera_pose(self) -> Pose:
        return self._camera_pose

    def set_camera_pose(self, pose: Pose) -> None:
        self._camera_pose = pose

    def get_camera_relative_pos(self, position: Position) -> Position:
        abs_pose = Pose(position, Orientation())
        return make_pose_rel(self._camera_pose, abs_pose).position

    def get_camera_absolute_pos(self, position: Position) -> Position:
        rel_pose = Pose(position, Orientation())
        return make_pose_abs(self._camera_pose, rel_pose).position

    @staticmethod
    def adjust_depth_position_to_rgb(position: Position) -> Position:
        # Depth camera is rotated by 1.3° down by x-axis
        # https://learn.microsoft.com/en-us/azure/kinect-dk/coordinate-systems
        #
        # Rotate upward 1.3° to match rgb camera axis
        adjuster = Pose(Position(-0.025, 0.0, 0.0), Orientation(-0.000383, 0.0, 0.0, 0.999997))
        return position.rotated(adjuster.orientation) + adjuster.position

    @property
    def log(self) -> logging.Logger:
        return self._kinect_logger

    @property
    def color_camera_params(self) -> CameraParameters | None:
        # https://github.com/microsoft/Azure-Kinect-Sensor-SDK/blob/develop/examples/opencv_compatibility/main.cpp
        # https://github.com/etiennedub/pyk4a/issues/69#issuecomment-698756626

        # order of parameters in JSON hopefully corresponds to order of parameters in this struct
        # https://microsoft.github.io/Azure-Kinect-Sensor-SDK/master/structk4a__calibration__intrinsic__parameters__t_1_1__param.html

        # for mode related offsets see this
        # https://github.com/microsoft/Azure-Kinect-Sensor-SDK/blob/90f77529f5ad19efd1e8f155a240c329e3bcbbdf/src/transformation/mode_specific_calibration.c#L95

        # "CALIBRATION_LensDistortionModelBrownConrady"

        img = self.color_image()

        # no need to handle depth camera parameters as we will always provide transformed depth image

        c = json.loads(self._k4a.calibration_raw)
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

                    # apply crop offset
                    cp.cy -= (img.width / 4 * 3 - img.width / 16 * 9) / 2
                    return cp

        except (KeyError, IndexError) as e:
            raise KinectAzureException("Failed to parse calibration.") from e

        return None

    def config(self) -> Config:
        return self._config

    def capture_buffer(self) -> deque[PyK4ACapture]:
        return self._capture_buffer

    def stable_buffer(self) -> deque[PyK4ACapture]:
        return self._capture_buffer.copy()

    def get_n_non_empty_captures(self, n: int) -> list[PyK4ACapture] | None:
        buffer: list[PyK4ACapture] = list()
        total_captures = 0
        if self._capture_thread is None:
            while len(buffer) < n:
                capture = self.__capture_from_device()
                skeleton = parse_skeleton(capture)
                if skeleton is not None:
                    buffer.append(capture)
                if total_captures > self.CAPTURE_BUFFER_CAP:
                    return None
                total_captures += 1
            return buffer
        else:
            stable_buffer = list(self.stable_buffer())
            for capture in stable_buffer[::-1]:
                skeleton = parse_skeleton(capture)
                if skeleton is not None:
                    buffer.append(capture)
                if len(buffer) == n:
                    return buffer[::-1]
        return None

    def get_non_empty_capture(self, tries: int = 5) -> PyK4ACapture | None:
        if self._capture_thread is None:
            for _ in range(tries):
                capture = self.__capture_from_device()
                skeleton = parse_skeleton(capture)
                if skeleton is not None:
                    return capture
        else:
            stable_buffer = list(self.stable_buffer())
            for capture in stable_buffer[::-1]:
                skeleton = parse_skeleton(capture)
                if skeleton is not None:
                    return capture
        return None

    def stable_buffer_len(self) -> int:
        return len(self._capture_buffer)

    def start_capturing(self):
        self._running_capture_thread = True

        def capture_forever() -> None:
            """Periodically capture frames from kinect."""

            counter = 0
            fps = 30
            while self._running_capture_thread:
                counter += 1
                start = time.time()
                capture = self.__capture_from_device()
                try:
                    _ = capture.body_skeleton
                except Exception as e:
                    self.log.exception(e)
                    continue

                end = time.time()
                self._capture_buffer.append(capture)
                if counter % fps == 0:
                    self.log.debug(f"{counter}: capturing took: {end - start}, captured: {fps} frames")
                time.sleep(0.005)

        self._capture_thread = threading.Thread(target=capture_forever)
        self._capture_thread.start()

    def __capture_from_device(self) -> PyK4ACapture:
        with self._lock:
            try:
                return self._k4a.get_capture(timeout=1000)
            except K4AException as e:
                self._kinect_logger.exception(e)
                raise KinectAzureException("Failed to get capture.") from e

    def capture(self) -> PyK4ACapture:
        if self._capture_thread is None:
            return self.__capture_from_device()
        else:
            if len(self._capture_buffer) == 0:
                time.sleep(0.2)
            return self._capture_buffer[-1]

    def color_image(self) -> Image.Image:
        capture = self.capture()

        if capture.color is None:
            raise KinectAzureException("Color image not available.")

        return Image.fromarray(capture.color, mode="RGBA")

    def _depth_image(self) -> np.ndarray:
        capture = self.capture()

        if capture.transformed_depth is None:
            raise KinectAzureException("Depth image not available.")

        return capture.transformed_depth

    def depth_image(self, num_frames: int = 1) -> Image.Image:
        assert num_frames > 0

        img = self._depth_image()
        array = img.astype(np.float32)

        for _ in range(num_frames - 1):
            array += self._depth_image().astype(np.float32)

        return Image.fromarray((array / num_frames).astype(img.dtype))

    def sync_images(self) -> ColorAndDepthImage:
        capture = self.capture()

        if not capture.color or not capture.depth:
            raise KinectAzureException("Color/depth image not available.")

        return ColorAndDepthImage(Image.fromarray(capture.color), Image.fromarray(capture.transformed_depth))

    def cleanup(self) -> None:
        if self._capture_thread is not None:
            self._running_capture_thread = False
            self._capture_thread.join(2)

        self._k4a.stop()

    def get_skeleton(self, body_id: int = 0) -> np.ndarray | None:
        capture = self.capture()
        return parse_skeleton(capture, body_id)

    def skeleton_image(self, raw: bool = False) -> Image.Image | np.ndarray:
        capture = self.capture()

        if capture.color is None:
            raise KinectAzureException("Color image not available.")

        frame = capture.color

        body_skeleton = capture.body_skeleton
        if body_skeleton is not None:
            for body_index in range(body_skeleton.shape[0]):
                skeleton = body_skeleton[body_index, :, :]
                for joint_index in range(skeleton.shape[0]):
                    if skeleton[joint_index, -1] != 1:
                        continue

                    x, y = skeleton[joint_index, (-3, -2)].astype(int)
                    cv2.circle(frame, (x, y), 12, (50, 50, 50), thickness=-1, lineType=cv2.FILLED)
                    cv2.putText(frame, str(joint_index), (x, y), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 0), 2, cv2.LINE_AA)
                if skeleton.shape[0] > 0:
                    # Display body id
                    cv2.putText(
                        frame,
                        f"Body id: {body_index}",
                        skeleton[1, (-3, -2)].astype(int),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        1,
                        (0, 255, 0),
                        2,
                        cv2.LINE_AA,
                    )

        if raw:
            return frame
        else:
            return Image.fromarray(frame, mode="RGBA")

    def get_bodies(self) -> np.ndarray | None:
        return self.capture().body_skeleton

    def get_video_feed(self) -> Generator[bytes, None, None]:
        """Get video feed that will be shown in browser."""
        while True:
            frame = self.skeleton_image(raw=True)
            # lower quality for smooth network transfer
            encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), 30]
            buffer = cv2.imencode(".jpg", frame, encode_param)[1]
            buffer_encode = np.array(buffer)
            frame = buffer_encode.tobytes()
            yield b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + frame + b"\r\n"
