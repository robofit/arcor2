from dataclasses import dataclass
from typing import Optional

from arcor2 import rest
from arcor2.data.common import ActionMetadata, Pose, Position, StrEnum
from arcor2.object_types.abstract import Generic

from .fit_common_mixin import FitCommonMixin, UrlSettings  # noqa:ABS101


class Color(StrEnum):
    ANY: str = "ANY"
    RED: str = "RED"
    GREEN: str = "GREEN"
    BLUE: str = "BLUE"
    YELLOW: str = "YELLOW"


@dataclass
class CubeTrackerSettings(UrlSettings):
    url: str = "http://fit-demo-cube-tracker:5021"


class CubeTracker(FitCommonMixin, Generic):
    _ABSTRACT = False

    def __init__(
        self,
        obj_id: str,
        name: str,
        settings: CubeTrackerSettings,
    ) -> None:
        super(CubeTracker, self).__init__(obj_id, name, settings)

        if self._started():
            self._stop()

        self._start()

    def _start(self) -> None:
        rest.call(rest.Method.PUT, f"{self.settings.url}/state/start")

    def _stop(self) -> None:
        rest.call(rest.Method.PUT, f"{self.settings.url}/state/stop")

    def cleanup(self) -> None:
        super(CubeTracker, self).cleanup()
        self._stop()

    def is_cube_in_area(
        self,
        position: Position,
        max_distance: float = 2,
        color: Color = Color.ANY,
        *,
        an: Optional[str] = None,
    ) -> bool:
        """Gets the nearest cube to the point of interest.

        :param position: Point to which the nearest cube is searched
        :param max_distance: Maximum distance between point and cube, defaults to 2
        :param color: Color of the cube, defaults to Color.ANY
        :return: Pose of the nearest cube
        """
        return rest.call(
            rest.Method.PUT,
            f"{self.settings.url}/cube/is-in-area",
            body=position,
            params={
                "max_distance": max_distance,
                "color": color.name,
            },
            raw_params=True,
            return_type=bool,
        )

    def get_nearest_cube(
        self,
        position: Position,
        offset_x: float = 0,
        offset_y: float = 0,
        offset_z: float = 0.0125,
        max_distance: float = 2,
        color: Color = Color.ANY,
        *,
        an: Optional[str] = None,
    ) -> Pose:
        """Gets the nearest cube to the point of interest.

        :param position: Point to which the nearest cube is searched
        :param offset_x: Offset on x axis, defaults to 0
        :param offset_y: Offset on y axis, defaults to 0
        :param offset_z: Offset on z axis, defaults to 0.0125
        :param max_distance: Maximum distance between point and cube, defaults to 2
        :param color: Color of the cube, defaults to Color.ANY
        :return: Pose of the nearest cube
        """
        return rest.call(
            rest.Method.PUT,
            f"{self.settings.url}/cube/nearest",
            body=position,
            params={
                "max_distance": max_distance,
                "offset_x": offset_x,
                "offset_y": offset_y,
                "offset_z": offset_z,
                "color": color.name,
            },
            raw_params=True,
            return_type=Pose,
        )

    def get_farthest_cube(
        self,
        position: Position,
        max_distance: float = 2,
        offset_x: float = 0,
        offset_y: float = 0,
        offset_z: float = 0.0125,
        color: Color = Color.ANY,
        *,
        an: Optional[str] = None,
    ) -> Pose:
        """Gets the farthest cube from the point of interest.

        :param position: Point to which the farthest cube is searched
        :param offset_x: Offset on x axis, defaults to 0
        :param offset_y: Offset on y axis, defaults to 0
        :param offset_z: Offset on z axis, defaults to 0.0125
        :param max_distance: Maximum distance between point and cube, defaults to 2
        :param color: Color of the cube, defaults to Color.ANY
        :return: Pose of the farthest cube
        """
        return rest.call(
            rest.Method.PUT,
            f"{self.settings.url}/cube/farthest",
            body=position,
            params={
                "max_distance": max_distance,
                "offset_x": offset_x,
                "offset_y": offset_y,
                "offset_z": offset_z,
                "color": color.name,
            },
            raw_params=True,
            return_type=Pose,
        )

    is_cube_in_area.__action__ = ActionMetadata()  # type: ignore
    get_nearest_cube.__action__ = ActionMetadata()  # type: ignore
    get_farthest_cube.__action__ = ActionMetadata()  # type: ignore
