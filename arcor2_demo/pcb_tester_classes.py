#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from random import choice
from typing import cast
from arcor2_demo.arcor2_classes import Pose, WorldObject, Robot, Arcor2Exception


class KinaliAPI:  # TODO singleton?
    """
    Provides thread-safe interface to the API
    """

    def __init__(self, ip: str, port: int):

        self._websocket = None


class FakeKinaliAPI:
    """
    Provides simulated API - for testing.
    """
    pass


class PCB(WorldObject):

    def __init__(self, pcb_type: str, max_attempts: int):

        super(PCB, self).__init__(child_limit=1)

        self.pcb_type = pcb_type
        self.attempt = 0
        self.max_attempts = max_attempts


class DataMatrixLabel(WorldObject):

    def __init__(self, pose: Pose) -> None:
        super(DataMatrixLabel, self).__init__(child_limit=0, pose=pose)


class AuboRobot(Robot):

    SUCTION = 0
    GRIPPER = 1

    def __init__(self, api: KinaliAPI) -> None:
        self._api = api
        super(AuboRobot, self).__init__()


class OkPCB(PCB):

    def __init__(self, pcb: PCB) -> None:

        # TODO is there a more elegant way how to 'upgrade' a class?
        self.pcb_type = pcb.pcb_type
        self.pose = pcb.pose
        self._child_limit = pcb._child_limit
        self._contains = pcb._contains
        self.attempt = pcb.attempt
        self.max_attempts = pcb.max_attempts


class NokPCB(PCB):

    def __init__(self, pcb: PCB) -> None:

        self.pcb_type = pcb.pcb_type
        self.pose = pcb.pose
        self._child_limit = pcb._child_limit
        self._contains = pcb._contains
        self.attempt = pcb.attempt
        self.max_attempts = pcb.max_attempts


class DataMatrixPrinter(WorldObject):

    def __init__(self, api: KinaliAPI) -> None:

        self._api = api
        super(DataMatrixPrinter, self).__init__(child_limit=1)

    def print(self, pcb: PCB) -> None:

        if isinstance(pcb, OkPCB):
            pass
        elif isinstance(pcb, NokPCB):
            pass

        self.add_child(DataMatrixLabel(pose=Pose()))

    def pick_label_blocking(self, robot: AuboRobot) -> DataMatrixLabel:

        label = cast(DataMatrixLabel, self.childs()[0])
        robot.pick(label, AuboRobot.SUCTION)
        self.remove_child(label)
        return label


class PCBTesterException(Arcor2Exception):
    pass


class PCBTester(WorldObject):

    def __init__(self, api: KinaliAPI, tester_id: str) -> None:

        super(PCBTester, self).__init__(child_limit=1)

        self._api = api
        self.tester_id = tester_id
        self.test_in_progress = False
        # TODO get tester pose from api

    def place_pcb_blocking(self, robot: AuboRobot, pcb: PCB) -> None:

        if pcb.attempt >= pcb.max_attempts:
            raise PCBTesterException("Max attempts for PCB reached.")

        robot.place_to(Pose(), robot.GRIPPER)
        self.add_child(pcb)
        # TODO exception on failure

    def test_run(self) -> None:

        if self.test_in_progress:
            raise PCBTesterException("Test already running.")

        if not self.childs():
            raise PCBTesterException("No PCB in the tester.")

        self.test_in_progress = True

        # TODO call API - exception on failure

    def pick_pcb_blocking(self, robot: AuboRobot) -> PCB:

        # TODO wait for test result
        # TODO consider case when test was not started - just pick pcb...
        self.test_in_progress = False

        try:
            pcb = cast(PCB, self.childs()[0])
        except IndexError:
            raise PCBTesterException("There is no PCB in the tester!")
        pcb.attempt += 1
        self.remove_child(pcb)

        if type(pcb) == PCB:
            pcb = choice((OkPCB, OkPCB, OkPCB, NokPCB))(
                pcb)  # now, the pcb has different type

        robot.pick(pcb, robot.GRIPPER)

        return pcb


class PCBBin(WorldObject):

    def __init__(self, api: KinaliAPI) -> None:

        self._api = api
        self.pose = Pose()  # TODO get from API?
        super(PCBBin, self).__init__()

    # TODO should this be non-blocking?
    def detect_blocking(self, pcb: PCB, attempts: int = 5) -> None:

        # pose = self.api.detect(pcb.pcb_type)
        pcb.pose = Pose()

    def pick_blocking(self, robot: AuboRobot, pcb: PCB) -> None:

        assert pcb.pose is not None

        robot.pick(pcb, robot.SUCTION)


class UnorganizedOutputBox(WorldObject):  # TODO limit capacity?

    def __init__(self, pose: Pose) -> None:

        super(UnorganizedOutputBox, self).__init__(pose)

    def place_blocking(self, robot: AuboRobot, pcb: PCB) -> None:

        robot.place_to(Pose(), robot.SUCTION)
        pcb.pose = None
        self.add_child(pcb)


class ClampException(Arcor2Exception):
    pass


class Clamp(WorldObject):

    def __init__(self, api: KinaliAPI) -> None:

        self._api = api
        super(Clamp, self).__init__()

    def pick_blocking(self, robot: AuboRobot, method: int) -> PCB:
        """
        Method specifies whether PCB should be picked-up with suction cup or with a gripper
        """

        assert len(self.childs()) == 1

        pcb = cast(PCB, self._contains[0])

        # TODO API - release command
        robot.pick(pcb, method)
        self.remove_child(pcb)

        return pcb

    def place_blocking(self, robot: AuboRobot, method: int) -> None:

        assert isinstance(robot.holding(method), PCB)
        self.add_child(robot.place_to(Pose(), method))
        # TODO API - catch command

    def stick_label_blocking(self, robot: AuboRobot) -> None:

        if not isinstance(robot.holding(robot.SUCTION), DataMatrixLabel):
            raise ClampException("Robot does not hold DM label.")

        try:
            self.childs()[0].add_child(robot.place_to(Pose(), robot.SUCTION))
        except IndexError:
            raise ClampException("There is no PCB in the clamp.")
