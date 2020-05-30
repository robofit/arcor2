import abc
from typing import List, FrozenSet

from arcor2.services import Service
from arcor2.data.common import Pose, Joint
from arcor2.data.object_type import MeshFocusAction
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
    def clear_collisions(self):
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
    def get_robot_ids(self) -> FrozenSet[str]:
        pass

    @abc.abstractmethod
    def get_robot_pose(self, robot_id: str) -> Pose:
        pass

    def stop(self, robot_id: str) -> None:
        pass

    @abc.abstractmethod
    def get_end_effectors_ids(self, robot_id: str) -> FrozenSet[str]:
        pass

    @abc.abstractmethod
    def get_end_effector_pose(self, robot_id: str, end_effector_id: str) -> Pose:
        pass

    @abc.abstractmethod
    def move(self, robot_id: str, end_effector_id: str, pose: Pose):
        pass

    @abc.abstractmethod
    def focus(self, mfa: MeshFocusAction) -> Pose:
        pass

    def inputs(self, robot_id: str) -> FrozenSet[str]:
        return frozenset()

    def outputs(self, robot_id: str) -> FrozenSet[str]:
        return frozenset()

    def get_input(self, robot_id: str, input_id: str) -> float:
        if input_id not in self.inputs(robot_id):
            raise ValueError("Invalid input_id.")

        return 0

    def set_output(self, robot_id: str, output_id: str, value: float) -> None:
        if output_id not in self.outputs(robot_id):
            raise ValueError("Invalid output_id.")
        return None

    @abc.abstractmethod
    def grippers(self, robot_id: str) -> FrozenSet[str]:
        return frozenset()

    @abc.abstractmethod
    def suctions(self, robot_id: str) -> FrozenSet[str]:
        return frozenset()

    @abc.abstractmethod
    def robot_joints(self, robot_id: str) -> List[Joint]:
        pass
