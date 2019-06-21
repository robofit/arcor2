#!/usr/bin/env python3
# -*- coding: utf-8 -*-


import json
from arcor2.generate_source import empty_script_tree, tree_to_script, add_import, add_cls_inst, add_method_call
from typed_ast.ast3 import Str, Load, Call, Name
from horast import parse

# TODO get rid of ast stuff here?


def main():

    tree = empty_script_tree()

    with open("scene.json") as scene_file:
        scene = json.load(scene_file)

    for scene_object in scene:

        # TODO add proper type to json
        add_import(tree, "arcor2.core", "WorldObject")

        inst_name = scene_object["_id"].lower().replace(' ', '_')

        add_cls_inst(tree, "WorldObject", inst_name, kwargs={"name": Str(scene_object["_id"])})

        for action_point in scene_object["ActionPoints"]:

            add_import(tree, "arcor2.data", "ActionPoint")
            add_import(tree, "arcor2.data", "Pose")

            position = []
            orientation = []

            for pos in action_point["Pose"]["Position"][1:-1].split(","):
                position.append(float(pos.strip()))

            for ori in action_point["Pose"]["Orientation"][1:-1].split(","):
                orientation.append(float(ori.strip()))

            # TODO action points should rather go into resources and then be referenced by id/name
            add_method_call(tree, inst_name, "add_action_point", True,
                            [Call(func=Name(id="ActionPoint", ctx=Load()),
                                      args=[Str(action_point["_id"]),
                                            Call(func=Name(id="Pose", ctx=Load()),
                                                    # TODO is this the best way?
                                                     args=[parse(str(position)), parse(str(orientation))], keywords=[])
                                            ],
                                      keywords=[])])

    tree_to_script(tree, "load_json_output.py")


if __name__ == "__main__":
    main()
