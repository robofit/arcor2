import abc
from typing import List, Set

from arcor2.data.common import Joint, Pose
from arcor2.data.object_type import MeshFocusAction
from arcor2.object_types import Generic
from arcor2.services.service import Service


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
    def clear_collisions(self) -> None:
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
        raise NotImplementedError("The robot can't be stopped.")

    @abc.abstractmethod
    def get_end_effectors_ids(self, robot_id: str) -> Set[str]:
        pass

    @abc.abstractmethod
    def get_end_effector_pose(self, robot_id: str, end_effector_id: str) -> Pose:
        pass

    def move_to_pose(self, robot_id: str, end_effector_id: str, target_pose: Pose, speed: float) -> None:
        """
        Move given robot's end effector to the selected pose.
        :param robot_id:
        :param end_effector_id:
        :param target_pose:
        :param speed:
        :return:
        """

        assert .0 <= speed <= 1.
        raise NotImplementedError("Service does not support moving robot's to pose.")

    def move_to_joints(self, robot_id: str, target_joints: List[Joint], speed: float) -> None:
        """
        Sets target joint values.
        :param robot_id:
        :param target_joints:
        :param speed:
        :return:
        """

        assert .0 <= speed <= 1.
        raise NotImplementedError("Service does not support moving robots to joints.")

    @abc.abstractmethod
    def focus(self, mfa: MeshFocusAction) -> Pose:
        pass

    def inputs(self, robot_id: str) -> Set[str]:
        return set()

    def outputs(self, robot_id: str) -> Set[str]:
        return set()

    def get_input(self, robot_id: str, input_id: str) -> float:
        if input_id not in self.inputs(robot_id):
            raise ValueError("Invalid input_id.")

        return 0

    def set_output(self, robot_id: str, output_id: str, value: float) -> None:
        if output_id not in self.outputs(robot_id):
            raise ValueError("Invalid output_id.")
        return None

    @abc.abstractmethod
    def grippers(self, robot_id: str) -> Set[str]:
        return set()

    @abc.abstractmethod
    def suctions(self, robot_id: str) -> Set[str]:
        return set()

    @abc.abstractmethod
    def robot_joints(self, robot_id: str) -> List[Joint]:
        pass
