#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import copy
import pytest  # type: ignore

from arcor2.data import Project, Scene
from arcor2.source.logic import program_src, get_logic_from_source
from arcor2.source import SourceException
from arcor2.helpers import built_in_types_names, clear_project_logic


def copy_wo_logic(source_project: Project) -> Project:

    project = copy.deepcopy(source_project)
    clear_project_logic(project)
    return project


VALID_PROJECT = Project.from_dict(
    {'id': 'demo_v0',
     'scene_id': 'jabloPCB/scenes/default',
     'objects': [
         {'id': 'BoxIN',
          'action_points': [
              {'id': 'transfer',
               'pose': {'position': {'x': 0.5, 'y': 0.6, 'z': 0}, 'orientation': {'x': 0, 'y': 0, 'z': 0, 'w': 1}},
               'actions': [
                   {'id': 'MoveToBoxIN',
                    'type': 'robot/move_to',
                    'parameters': [
                        {'id': 'end_effector', 'type': 'string', 'value': 'gripper1'},
                        {'id': 'target', 'type': 'ActionPoint', 'value': 'BoxIN.transfer'},
                        {'id': 'speed', 'type': 'double', 'value': 15}],
                    'inputs': [{'default': 'start'}],
                    'outputs': [{'default': 'MoveToTester'}]}]}]},
         {'id': 'Tester',
          'action_points': [
              {'id': 'input',
               'pose': {'position': {'x': 0.5, 'y': 0.6, 'z': 0}, 'orientation': {'x': 0, 'y': 0, 'z': 0, 'w': 1}},
               'actions': [
                   {'id': 'MoveToTester',
                    'type': 'robot/move_to',
                    'parameters': [
                        {'id': 'end_effector', 'type': 'string', 'value': 'gripper1'},
                        {'id': 'target', 'type': 'ActionPoint', 'value': 'Tester.input'},
                        {'id': 'speed', 'type': 'double', 'value': 15}],
                    'inputs': [{'default': 'MoveToBoxIN'}],
                    'outputs': [{'default': 'MoveToBoxOUT'}]}]}]},
         {'id': 'BoxOUT',
          'action_points': [
              {'id': 'transfer',
               'pose': {'position': {'x': 0.5, 'y': 0.6, 'z': 0}, 'orientation': {'x': 0, 'y': 0, 'z': 0, 'w': 1}},
               'actions': [
                   {'id': 'MoveToBoxOUT',
                    'type': 'robot/move_to',
                    'parameters': [
                        {'id': 'end_effector', 'type': 'string', 'value': 'suction1'},
                        {'id': 'target', 'type': 'ActionPoint', 'value': 'Tester.input'},
                        {'id': 'speed', 'type': 'double', 'value': 15}],
                    'inputs': [{'default': 'MoveToTester'}],
                    'outputs': [{'default': 'end'}]}]}]}]
     }
)


VALID_PROJECT_WO_LOGIC = copy_wo_logic(VALID_PROJECT)

VALID_SCENE = Scene.from_dict(
    {'id': 'jabloPCB/scenes/default',
     'objects': [
         {'id': 'Robot',
          'type': 'Robot',
          'pose': {'position': {'x': 0.1, 'y': 0.2, 'z': 0}, 'orientation': {'x': 0, 'y': 0, 'z': 0, 'w': 1}}},
         {'id': 'Tester',
          'type': 'Tester',
          'pose': {'position': {'x': 0.5, 'y': 0.6, 'z': 0}, 'orientation': {'x': 0, 'y': 0, 'z': 0, 'w': 1}}},
         {'id': 'BoxIN',
          'type': 'Box',
          'pose': {'position': {'x': 0.8, 'y': 1.2, 'z': 0}, 'orientation': {'x': 0, 'y': 0, 'z': 0, 'w': 1}}},
         {'id': 'BoxOUT',
          'type': 'Box',
          'pose': {'position': {'x': 1.8, 'y': 1.2, 'z': 0}, 'orientation': {'x': 0, 'y': 0, 'z': 0, 'w': 1}}}]
     }
)

VALID_PROJECTS = (VALID_PROJECT, VALID_PROJECT_WO_LOGIC)

VALID_SOURCE = """#!/usr/bin/env python3
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


def test_valid():

    for valid_project in VALID_PROJECTS:

        project = copy.deepcopy(valid_project)
        get_logic_from_source(VALID_SOURCE, project)
        assert VALID_PROJECT == project


def test_unknown_action():

    for valid_project in VALID_PROJECTS:

        project = copy.deepcopy(valid_project)
        invalid_source = VALID_SOURCE.replace("MoveToTester", "MoveToSomewhereElse")

        with pytest.raises(SourceException):
            get_logic_from_source(invalid_source, project)


def test_totally_invalid_source():

    for valid_project in VALID_PROJECTS:

        project = copy.deepcopy(valid_project)
        with pytest.raises(SourceException):
            get_logic_from_source("", project)


def test_valid_with_different_logic():

    for valid_project in VALID_PROJECTS:

        project = copy.deepcopy(valid_project)
        get_logic_from_source(VALID_SOURCE_WITH_DIFFERENT_ACTION_ORDER, project)
        assert valid_project != project


def test_missing_action():

    project = copy.deepcopy(VALID_PROJECT)
    delete_first_action_found(project)

    with pytest.raises(SourceException):
        get_logic_from_source(VALID_SOURCE, project)


def test_duplicate_action():

    for valid_project in VALID_PROJECTS:

        project = copy.deepcopy(valid_project)
        invalid_source = VALID_SOURCE.replace("MoveToTester", "MoveToBoxOUT")

        with pytest.raises(SourceException):
            get_logic_from_source(invalid_source, project)


def test_from_source_to_json_and_back():

    source = program_src(VALID_PROJECT, VALID_SCENE, built_in_types_names())
    assert source == VALID_SOURCE
    project = copy.deepcopy(VALID_PROJECT_WO_LOGIC)
    get_logic_from_source(source, project)
    assert VALID_PROJECT == project
