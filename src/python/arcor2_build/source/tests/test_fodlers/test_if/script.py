#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from object_types.random_actions import RandomActions
from action_points import ActionPoints
from arcor2_runtime.resources import Resources
from arcor2_runtime.exceptions import print_exception


def main(res: Resources) -> None:
    aps = ActionPoints(res)
    random_actions: RandomActions = res.objects['obj_43dfe4677b004fab91b31a48f86fa201']
    scene_id = 'scn_94db6c5dfe7040f6b027c3a9b558d937'
    project_id = 'pro_2e99c03e10554ed68f3ed5e320aa5190'
    while True:
        random_double1 = random_actions.random_double(1.0, 100.0, an='random_double1')
        random_bool1 = random_actions.random_bool(an='random_bool1')
        if random_bool1 == False:
            random_double2 = random_actions.random_double(random_double1, 100.0, an='random_double2')
        elif random_bool1 == True:
            random_bool2 = random_actions.random_bool(an='random_bool2')
            if random_bool2 == True:
                continue
            elif random_bool2 == False:
                random_double3 = random_actions.random_double(random_double1, 200.0, an='random_double3')
        random_double4 = random_actions.random_double(random_double1, 300.0, an='random_double4')

if __name__ == '__main__':
    try:
        with Resources() as res:
            main(res)
    except Exception as e:
        print_exception(e)