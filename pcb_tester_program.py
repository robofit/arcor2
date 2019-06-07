#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import time
from arcor2.core import Arcor2Exception
from arcor2.pcb_tester_classes import KinaliAPI, AuboRobot, PCBBin, DataMatrixPrinter,\
    UnorganizedOutputBox, Pose, PCB, Clamp, NokPCB

# Extended (instrumented) classes could be imported instead of pure ones in order to provide interactive features
# std. / extended will be imported based on e.g. script argument
from arcor2.pcb_tester_interaction_classes import PCBTesterInt as PCBTester


def fce_001(pcb_bin: PCBBin, robot: AuboRobot,
            clamp: Clamp, pcb_tester: PCBTester) -> None:
    """
    Automatically generated function - code duplication detected
    """

    if pcb_tester.childs():
        return

    pcb = PCB("big_pcb_123", max_attempts=5)
    pcb_bin.io_detect_blocking(pcb)
    pcb_bin.io_pick_blocking(robot, pcb)

    clamp.io_place_blocking(robot, robot.SUCTION)
    pcb = clamp.io_pick_blocking(robot, robot.GRIPPER)

    pcb_tester.io_place_pcb_blocking(robot, pcb)
    pcb_tester.io_test_run()


def fce_002(dm_printer: DataMatrixPrinter, clamp: Clamp, pcb: PCB,
            robot: AuboRobot, box: UnorganizedOutputBox) -> None:
    """
    Automatically generated function - code duplication detected
    """

    dm_printer.io_print(pcb)
    clamp.io_place_blocking(robot, robot.GRIPPER)
    dm_printer.io_pick_label_blocking(robot)
    clamp.io_stick_label_blocking(robot)
    clamp.io_pick_blocking(robot, robot.SUCTION)
    box.io_place_blocking(robot, pcb)


def fce_003(pcb_tester: PCBTester, robot: AuboRobot,
            dm_printer: DataMatrixPrinter, clamp: Clamp,
            box_nok: UnorganizedOutputBox, box_ok: UnorganizedOutputBox) -> None:
    """
    Automatically generated function - code duplication detected
    """

    # TODO it might be good to know test result before picking up the board
    pcb = pcb_tester.io_pick_pcb_blocking(robot)

    if isinstance(pcb, NokPCB):
        if pcb.attempt >= pcb.max_attempts:
            fce_002(dm_printer, clamp, pcb, robot, box_nok)
        else:
            pcb_tester.io_place_pcb_blocking(robot, pcb)
            pcb_tester.io_test_run()
    else:
        fce_002(dm_printer, clamp, pcb, robot, box_ok)


def main() -> None:

    api = KinaliAPI("192.168.1.1", 1234)

    # definition of the environment
    robot = AuboRobot(api)  # robot origin == world origin
    pcb_bin = PCBBin(api)  # there is only one bin, it get pose from API (?)

    # ...poses of the boxes are given by the user
    box_ok = UnorganizedOutputBox(pose=Pose())
    box_nok = UnorganizedOutputBox(pose=Pose())

    # TODO shall user set how to put PCB into the tester?
    pcb_tester1 = PCBTester(api, tester_id="t1")
    pcb_tester2 = PCBTester(api, tester_id="t2")

    dm_printer = DataMatrixPrinter(api)  # TODO pose from API or user?
    clamp = Clamp(api)  # TODO pose from API or user?

    while True:  # automatically "optimized" program

        try:
            fce_001(pcb_bin, robot, clamp, pcb_tester1)
            fce_001(pcb_bin, robot, clamp, pcb_tester2)
            fce_003(pcb_tester1, robot, dm_printer, clamp, box_nok, box_ok)
            fce_003(pcb_tester2, robot, dm_printer, clamp, box_nok, box_ok)
        except Arcor2Exception as e:
            print(e)
            return

        print("OK: {}, NOK: {}".format(
            len(box_ok.childs()), len(box_nok.childs())))
        time.sleep(1)


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("Shutting down")
