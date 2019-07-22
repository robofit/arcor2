#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import unittest
from arcor2.data import Project
from arcor2.generate_source import get_logic_from_source, GenerateSourceException
import copy

VALID_PROJECT = Project.from_dict(
    {'id': 'demo_v0', 'scene_id': 'jabloPCB/scenes/default', 'objects': [{'id': 'BoxIN', 'action_points': [{'id': 'transfer', 'pose': {'position': {'x': 0.5, 'y': 0.6, 'z': 0}, 'orientation': {'x': 0, 'y': 0, 'z': 0, 'w': 1}}, 'actions': [{'id': 'MoveToBoxIN', 'type': 'robot/move_to', 'parameters': [{'id': 'end_effector', 'type': 'string', 'value': 'gripper1'}, {'id': 'target', 'type': 'ActionPoint', 'value': 'BoxIN.transfer'}, {'id': 'speed', 'type': 'double', 'value': 15}], 'inputs': [{'default': 'start'}], 'outputs': [{'default': 'MoveToTester'}]}]}]}, {'id': 'Tester', 'action_points': [{'id': 'input', 'pose': {'position': {'x': 0.5, 'y': 0.6, 'z': 0}, 'orientation': {'x': 0, 'y': 0, 'z': 0, 'w': 1}}, 'actions': [{'id': 'MoveToTester', 'type': 'robot/move_to', 'parameters': [{'id': 'end_effector', 'type': 'string', 'value': 'gripper1'}, {'id': 'target', 'type': 'ActionPoint', 'value': 'Tester.input'}, {'id': 'speed', 'type': 'double', 'value': 15}], 'inputs': [{'default': 'MoveToBoxIN'}], 'outputs': [{'default': 'MoveToBoxOUT'}]}]}]}, {'id': 'BoxOUT', 'action_points': [{'id': 'transfer', 'pose': {'position': {'x': 0.5, 'y': 0.6, 'z': 0}, 'orientation': {'x': 0, 'y': 0, 'z': 0, 'w': 1}}, 'actions': [{'id': 'MoveToBoxOUT', 'type': 'robot/move_to', 'parameters': [{'id': 'end_effector', 'type': 'string', 'value': 'suction1'}, {'id': 'target', 'type': 'ActionPoint', 'value': 'Tester.input'}, {'id': 'speed', 'type': 'double', 'value': 15}], 'inputs': [{'default': 'MoveToTester'}], 'outputs': [{'default': 'end'}]}]}]}]}
)
VALID_PROJECT_WO_LOGIC = Project.from_dict(
    {'id': 'demo_v0', 'scene_id': 'jabloPCB/scenes/default', 'objects': [{'id': 'BoxIN', 'action_points': [{'id': 'transfer', 'pose': {'position': {'x': 0.5, 'y': 0.6, 'z': 0}, 'orientation': {'x': 0, 'y': 0, 'z': 0, 'w': 1}}, 'actions': [{'id': 'MoveToBoxIN', 'type': 'robot/move_to', 'parameters': [{'id': 'end_effector', 'type': 'string', 'value': 'gripper1'}, {'id': 'target', 'type': 'ActionPoint', 'value': 'BoxIN.transfer'}, {'id': 'speed', 'type': 'double', 'value': 15}], 'inputs': [], 'outputs': []}]}]}, {'id': 'Tester', 'action_points': [{'id': 'input', 'pose': {'position': {'x': 0.5, 'y': 0.6, 'z': 0}, 'orientation': {'x': 0, 'y': 0, 'z': 0, 'w': 1}}, 'actions': [{'id': 'MoveToTester', 'type': 'robot/move_to', 'parameters': [{'id': 'end_effector', 'type': 'string', 'value': 'gripper1'}, {'id': 'target', 'type': 'ActionPoint', 'value': 'Tester.input'}, {'id': 'speed', 'type': 'double', 'value': 15}], 'inputs': [], 'outputs': []}]}]}, {'id': 'BoxOUT', 'action_points': [{'id': 'transfer', 'pose': {'position': {'x': 0.5, 'y': 0.6, 'z': 0}, 'orientation': {'x': 0, 'y': 0, 'z': 0, 'w': 1}}, 'actions': [{'id': 'MoveToBoxOUT', 'type': 'robot/move_to', 'parameters': [{'id': 'end_effector', 'type': 'string', 'value': 'suction1'}, {'id': 'target', 'type': 'ActionPoint', 'value': 'Tester.input'}, {'id': 'speed', 'type': 'double', 'value': 15}], 'inputs': [], 'outputs': []}]}]}]}
)

VALID_PROJECTS = (VALID_PROJECT, VALID_PROJECT_WO_LOGIC)

VALID_SOURCE = """
#!/usr/bin/env python3
# -*- coding: utf-8 -*-


from object_types.box import Box
from object_types.tester import Tester
from arcor2.object_types import Robot
from resources import Resources


def main() -> None:
    res = Resources()
    robot: Robot = res.objects['Robot']
    tester: Tester = res.objects['Tester']
    box_in: Box = res.objects['BoxIN']
    box_out: Box = res.objects['BoxOUT']
    while True:
        robot.move_to(**res.MoveToBoxIN)
        robot.move_to(**res.MoveToTester)
        robot.move_to(**res.MoveToBoxOUT)


if (__name__ == '__main__'):
    main()
"""

VALID_SOURCE_WITH_DIFFERENT_ACTION_ORDER = """
#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from object_types.box import Box
from object_types.tester import Tester
from arcor2.object_types import Robot
from resources import Resource


def main() -> None:

    res = Resources()
    robot: Robot = res.objects['Robot']
    tester: Tester = res.objects['Tester']
    box_in: Box = res.objects['BoxIN']
    box_out: Box = res.objects['BoxOUT']

    while True:
        robot.move_to(**res.MoveToBoxOUT)
        robot.move_to(**res.MoveToBoxIN)
        robot.move_to(**res.MoveToTester)


if (__name__ == '__main__'):
    main()
"""


def delete_first_action_found(project: Project):

    for obj in project.objects:
        for act_point in obj.action_points:
            if act_point.actions:
                del act_point.actions[0]
                return


class GetLogicFromSource(unittest.TestCase):

    def test_valid(self):

        for valid_project in VALID_PROJECTS:

            project = copy.deepcopy(valid_project)
            get_logic_from_source(VALID_SOURCE, project)
            self.assertEqual(VALID_PROJECT, project)

    def test_unknown_action(self):

        for valid_project in VALID_PROJECTS:

            project = copy.deepcopy(valid_project)
            invalid_source = VALID_SOURCE.replace("MoveToTester", "MoveToSomewhereElse")

            with self.assertRaises(GenerateSourceException):
                get_logic_from_source(invalid_source, project)

    def test_totally_invalid_source(self):

        for valid_project in VALID_PROJECTS:

            project = copy.deepcopy(valid_project)
            with self.assertRaises(GenerateSourceException):
                get_logic_from_source("", project)

    def test_valid_with_different_logic(self):

        for valid_project in VALID_PROJECTS:

            project = copy.deepcopy(valid_project)
            get_logic_from_source(VALID_SOURCE_WITH_DIFFERENT_ACTION_ORDER, project)
            self.assertNotEqual(valid_project, project)

    def test_missing_action(self):

        project = copy.deepcopy(VALID_PROJECT)
        delete_first_action_found(project)

        with self.assertRaises(GenerateSourceException):
            get_logic_from_source(VALID_SOURCE, project)

    def test_duplicate_action(self):

        for valid_project in VALID_PROJECTS:

            project = copy.deepcopy(valid_project)
            invalid_source = VALID_SOURCE.replace("MoveToTester", "MoveToBoxOUT")

            with self.assertRaises(GenerateSourceException):
                get_logic_from_source(invalid_source, project)


if __name__ == '__main__':
    unittest.main()
