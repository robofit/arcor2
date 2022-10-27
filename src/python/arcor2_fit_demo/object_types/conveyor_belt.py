import time
from dataclasses import dataclass

from arcor2 import rest
from arcor2.data.common import ActionMetadata, Pose, StrEnum
from arcor2.data.object_type import Models
from arcor2.exceptions import Arcor2Exception
from arcor2.object_types.abstract import CollisionObject

from .fit_common_mixin import FitCommonMixin, UrlSettings  # noqa:ABS101


class Direction(StrEnum):

    FORWARD: str = "forward"
    BACKWARDS: str = "backwards"


@dataclass
class ConveyorBeltSettings(UrlSettings):

    url: str = "http://fit-demo-dobot-magician:5018"


class ConveyorBelt(FitCommonMixin, CollisionObject):

    mesh_filename = "conveyor_belt.fbx"
    _ABSTRACT = False

    def __init__(
        self,
        obj_id: str,
        name: str,
        pose: Pose,
        collision_model: Models,
        settings: ConveyorBeltSettings,
    ) -> None:

        super(ConveyorBelt, self).__init__(obj_id, name, pose, collision_model, settings)

        iter: int = 0
        while True:
            if self._started():
                break
            time.sleep(0.1)
            iter += 1

            if iter > 10:
                raise Arcor2Exception("Failed to connect to the Dobot Service.")

    def set_velocity(
        self, velocity: float = 0.5, direction: Direction = Direction.FORWARD, *, an: None | str = None
    ) -> None:
        """Belt will move indefinitely with given velocity.

        :param velocity:
        :param direction:
        :param an:
        :return:
        """

        assert 0.0 <= velocity <= 1.0

        rest.call(
            rest.Method.PUT,
            f"{self.settings.url}/conveyor/speed",
            params={"velocity": velocity * 100, "direction": direction},
        )

    set_velocity.__action__ = ActionMetadata()  # type: ignore

    def set_distance(
        self,
        velocity: float = 0.5,
        distance: float = 0.55,
        direction: Direction = Direction.FORWARD,
        *,
        an: None | str = None,
    ) -> None:
        """Belt will move by given distance.

        :param velocity:
        :param distance:
        :param direction:
        :param an:
        :return:
        """

        assert 0.0 <= velocity <= 1.0
        assert 0.0 <= distance <= 9999.0

        rest.call(
            rest.Method.PUT,
            f"{self.settings.url}/conveyor/distance",
            params={"velocity": velocity * 100, "distance": distance, "direction": direction},
        )

    set_distance.__action__ = ActionMetadata()  # type: ignore
