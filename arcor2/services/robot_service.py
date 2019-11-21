import abc
from typing import Set

from arcor2.services import Service
from arcor2.data.common import Pose
from arcor2.object_types import Generic


class RobotService(Service, metaclass=abc.ABCMeta):


    @abc.abstractmethod
    def add_collision(self, obj: Generic) -> None:
        """
        Adds collision model for object instance.
        :param obj:
        :return:
        """
        pass

    @abc.abstractmethod
    def remove_collision(self, obj: Generic) -> None:
        """
        Removes collision model for object instance.
        :param obj:
        :return:
        """
        pass

    @abc.abstractmethod
    def get_robot_ids(self) -> Set[str]:
        pass

    @abc.abstractmethod
    def get_robot_pose(self, robot_id: str) -> Pose:
        pass

    def stop(self, robot_id: str) -> None:
        pass

    @abc.abstractmethod
    def get_end_effectors_ids(self, robot_id: str) -> Set[str]:
        pass

    @abc.abstractmethod
    def get_end_effector_pose(self, robot_id: str, end_effector_id: str) -> Pose:
        pass

    @abc.abstractmethod
    def end_effector_move(self, robot_id: str, end_effector_id: str, pose: Pose):
        pass
