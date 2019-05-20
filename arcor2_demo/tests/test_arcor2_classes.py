#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import unittest
from arcor2_demo.arcor2_classes import Pose, WorldObject, WorldObjectException, Robot, RobotException


class TestWorldObject(unittest.TestCase):

    def test_childs(self):

        wo = WorldObject()
        self.assertEqual(len(wo.childs()), 0)

        wo2 = WorldObject()
        wo.add_child(wo2)
        self.assertEqual(len(wo.childs()), 1)

        with self.assertRaises(WorldObjectException):
            wo.add_child(wo2)

        self.assertEqual(len(wo.childs()), 1)

        wo.remove_child(wo2)
        self.assertEqual(len(wo.childs()), 0)

        wo = WorldObject(child_limit=0)

        with self.assertRaises(WorldObjectException):
            wo.add_child(wo2)

        self.assertEqual(len(wo.childs()), 0)

        with self.assertRaises(WorldObjectException):
            wo.remove_child(WorldObject())

    def test_pose(self):

        wo = WorldObject()

        self.assertEqual(wo.pose, None)

        wo = WorldObject(pose=Pose())

        self.assertIsInstance(wo.pose, Pose)


class TestRobot(unittest.TestCase):

    def test_pick_place(self):

        robot = Robot()

        with self.assertRaises(RobotException):
            robot.pick(WorldObject(), 0)

        wo = WorldObject(pose=Pose())

        robot.pick(wo, 0)

        with self.assertRaises(RobotException):
            robot.pick(wo, 0)

        robot.pick(wo, 1)

        with self.assertRaises(RobotException):
            robot.pick(wo, 1)

        with self.assertRaises(RobotException):
            robot.place_to(Pose(), "non-existent-end-effector")

        robot.place_to(Pose(), 0)
        robot.place_to(Pose(), 1)

        with self.assertRaises(RobotException):
            robot.place_to(Pose(), 0)

        with self.assertRaises(RobotException):
            robot.place_to(Pose(), 1)

if __name__ == '__main__':
    unittest.main()
