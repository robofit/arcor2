import cv2
import pyk4a
from pyk4a import Config, PyK4A


def main() -> None:
    k4a = PyK4A(
        Config(
            color_resolution=pyk4a.ColorResolution.RES_720P,
            depth_mode=pyk4a.DepthMode.NFOV_UNBINNED,
            synchronized_images_only=True,
        )
    )
    k4a.start()

    while 1:
        capture = k4a.get_capture()
        if capture.color:
            cv2.imshow("k4a", capture.color[:, :, :3])
            key = cv2.waitKey(10)
            if key != -1:
                cv2.destroyAllWindows()
                break
    k4a.stop()


if __name__ == "__main__":
    main()
