#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import coloredlogs  # type: ignore
import logging
from arcor2_demo.pcb_tester_classes import PCBTester, AuboRobot, PCB, KinaliAPI
# from arcor2_msgs.msg import WorldObjectState

logger = logging.getLogger()
coloredlogs.install(level='DEBUG')


class PCBTesterInt(PCBTester):

    def __init__(self, api: KinaliAPI, tester_id: str) -> None:

        super(PCBTesterInt, self).__init__(api, tester_id)

        # self.state_publisher = rospy.Publish("/arcor2/objects/pcbtester/state", WorldObjectState)

    def place_pcb_blocking(self, robot: AuboRobot, pcb: PCB) -> None:

        logger.debug("{}: place_pcb_blocking start".format(
            self.tester_id))  # TODO publish it to ROS
        super(PCBTesterInt, self).place_pcb_blocking(robot, pcb)
        logger.debug("{}: place_pcb_blocking end".format(self.tester_id))

    def test_run(self) -> None:
        logger.debug(
            "{}: test_run start".format(
                self.tester_id))  # TODO publish it to ROS
        res = super(PCBTesterInt, self).test_run()
        logger.debug("{}: test_run end".format(self.tester_id))

    def pick_pcb_blocking(self, robot: AuboRobot) -> PCB:

        logger.debug("{}: pick_pcb_blocking start".format(
            self.tester_id))  # TODO publish it to ROS
        res = super(PCBTesterInt, self).pick_pcb_blocking(robot)
        logger.debug("{}: pick_pcb_blocking end".format(self.tester_id))
        return res
