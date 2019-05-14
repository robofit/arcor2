#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import unittest
from arcor2_demo.arcor2_classes import Pose, WorldObject, WorldObjectException, Robot, RobotException
from arcor2_demo.pcb_tester_classes import KinaliAPI, PCBTester, PCBTesterException, AuboRobot, PCB


class TestPCBTester(unittest.TestCase):

    def setUp(self) -> None:

        self.api = KinaliAPI("192.168.1.1", 1234)
        self.robot = AuboRobot(self.api)

    def test_pick_from_empty_tester(self):

        tester = PCBTester(self.api, "abc")
        with self.assertRaises(PCBTesterException):
            tester.pick_pcb_blocking(self.robot)

    def test_place_run_pick(self):

        tester = PCBTester(self.api, "abc")
        pcb = PCB(pcb_type="def", max_attempts=3)
        pcb.pose = Pose()

        self.robot.pick(pcb, self.robot.GRIPPER)

        tester.place_pcb_blocking(self.robot, pcb)
        tester.test_run()
        pcb2 = tester.pick_pcb_blocking(self.robot)

        self.assertEqual(pcb.pcb_type, pcb2.pcb_type)

    def test_run_empty(self):

        tester = PCBTester(self.api, "abc")

        with self.assertRaises(PCBTesterException):
            tester.test_run()

    def test_run_twice(self):

        tester = PCBTester(self.api, "abc")
        pcb = PCB(pcb_type="def", max_attempts=3)
        pcb.pose = Pose()

        self.robot.pick(pcb, self.robot.GRIPPER)

        tester.place_pcb_blocking(self.robot, pcb)
        tester.test_run()

        with self.assertRaises(PCBTesterException):
            tester.test_run()

    def test_attempts(self):

        tester = PCBTester(self.api, "abc")
        pcb = PCB(pcb_type="def", max_attempts=1)
        pcb.pose = Pose()

        self.assertEqual(pcb.attempt, 0)

        self.robot.pick(pcb, self.robot.GRIPPER)

        tester.place_pcb_blocking(self.robot, pcb)
        tester.test_run()
        pcb = tester.pick_pcb_blocking(self.robot)

        self.assertEqual(pcb.attempt, 1)

        with self.assertRaises(PCBTesterException):
            tester.place_pcb_blocking(self.robot, pcb)


if __name__ == '__main__':
    unittest.main()
