#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from random import choice
from arcor2_msgs.msg import WorldObjectState
import time
from typing import Union


# TODO projít video a sladit s Kapiho koncepty
# TODO kleště na přechycení desky (lepení štítku)
# TODO přepsání programu

class WorldObject(object):

    def __init__(self, position=None, orientation=None):

        self.contains = []


class Robot(object):
    """
    Abstract class representing robot (motion capabilities, sensors)
    """

    def __init__(self, api):

        self._api = api


class DataMatrixPrinter(WorldObject):

    def __init__(self, api):

        self.printed = False
        self._api = api

    def print(self, result: int) -> None:
        # self._api.print_label(callback=self.label_cb)
        return


class PCB(WorldObject):

    def __init__(self, max_attempts):

        self.attempt = 0
        self.max_attempts = max_attempts


class OkPCB(PCB):

    def __init__(self, pcb):

        self.attempt = pcb.attempt
        self.max_attempts = pcb.max_attempts


class NokPCB(PCB):

    def __init__(self, pcb):

        self.attempt = pcb.attempt
        self.max_attempts = pcb.max_attempts


class PCBTester(WorldObject):

    def __init__(self, api):

        self._api = api
        # TODO get tester pose from api

    def place_pcb(self, robot: Robot, pcb: PCB) -> None:

        # TODO robot stuff
        self.contains.append(pcb)
        # TODO run test (e.g. self._api.run_cmd("TESTER RUN"))
        # TODO exception on failure
        return

    def test_run(self) -> None:

        # TODO call API - exception on failure
        return

    # TODO somehow mark it as blocking
    def pick_pcb(self, robot: Robot) -> Union[OkPCB, NokPCB]:

        # TODO wait for test result

        pcb = self.contains[0]
        pcb.attempt += 1
        self.contains.remove(pcb)

        pcb = choice(OkPCB, NokPCB)(pcb)  # now, the pcb has different type

        # TODO do something with robot...

        return pcb


class PCBTesterInt(PCBTester):

    def __init__(self, *args, **kwargs):

        super(PCBTester, self).__init__(args, kwargs)

        self.state_publisher = rospy.Publish("/arcor2/objects/pcbtester/state", WorldObjectState)

    def place_pcb(self, *args, **kwargs):

        # TODO publish start of method
        res = super(PCBTester, self).put_in(args, kwargs)
        # TODO publish end of method + result
        return res


class PCBBin(WorldObject):
    pass


class OutputBox(WorldObject):

    def place(self, robot: Robot, pcb: PCB) -> None:
        return


class AuboRobot(Robot):

    def __init__(self, api):

        self._api = api


class KinaliAPI(object):

    def __init__(self, ip, port):

        self._websocket = None


"""        
class ROSAPI(SystemAPI):
    pass
"""


def main():

    # definice prostredi - kde?


    api = KinaliAPI("192.168.1.1", 1234)

    robot = AuboRobot(api)  # robot je stred sveta, vse ostatni vzhledem k nemu
    bin = PCBBin(api)  # bin si zjisti z API svoji pozici, bude jen jeden

    # TODO bude krabice detekovaná (potom by se použilo box_id)
    #  nebo jen nějak nastavená uživatelem (potom by se použila pozice)?
    box_ok = OutputBox(api, box_id="abc", position=[1, 1, 1], orientation=[0, 0, 0, 1])
    box_nok = OutputBox(api, box_id="def", position=[1, 2, 1], orientation=[0, 0, 0, 1])

    # TODO bude uživatel nastavovat jak založit dps do testeru?
    pcb_tester1 = PCBTester(api, tester_id="fdeer")
    pcb_tester2 = PCBTester(api, tester_id="ewqrd")

    dm_printer = DataMatrixPrinter(api)

    while True:

        # ve vygenerovanem skriptu by toto bylo spise jako duplikovany kod pro tester1 a tester2
        for pcb_tester in (pcb_tester1, pcb_tester2):

            if not pcb_tester.contains:

                pcb = PCB()  # TODO parametr říkající jak to chytit

                if not bin.detect(pcb, attempts=5):
                    return 1  # TODO define program error codes

                if not bin.pick(robot, pcb):
                    continue

                # TODO přechycení - objekt pro kleště držící pcb

                if not pcb_tester.place_pcb(robot, pcb):
                    return 2

                # test now runs in background...

            else:

                if pcb_tester.done():

                    pcb = pcb_tester.pick_pcb(robot)

                    if pcb_tester.result() == PCBTester.TEST_OK:

                        box_ok.place(robot, pcb)

                    else:

                        pcb = pcb_tester.pick_pcb(robot)

                        if pcb.attempt < pcb.max_attempts:

                            pcb_tester.place_pcb(robot, pcb)

                        else:

                            box_nok.place(robot, pcb)

        time.sleep(1)


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("Shutting down")