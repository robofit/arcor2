#!/usr/bin/env python3
# -*- coding: utf-8 -*-


import json
from arcor2.generate_source import empty_script_tree, tree_to_script, add_import, add_cls_inst, add_method_call
import ast

# TODO get rid of ast stuff here?


def main():

    tree = empty_script_tree()

    with open("scene.json") as scene_file:
        scene = json.load(scene_file)

    for scene_object in scene:

        # TODO add proper type to json
        add_import(tree, "arcor2.core", "WorldObject")

        inst_name = scene_object["_id"].lower().replace(' ', '_')

        add_cls_inst(tree, "WorldObject", inst_name, kwargs={"name": ast.Str(scene_object["_id"])})

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
                            [ast.Call(func=ast.Name(id="ActionPoint", ctx=ast.Load()),
                                      args=[ast.Str(action_point["_id"]),
                                            ast.Call(func=ast.Name(id="Pose", ctx=ast.Load()),
                                                    # TODO is this the best way?
                                                     args=[ast.parse(str(position)), ast.parse(str(orientation))], keywords=[])
                                            ],
                                      keywords=[])])

    tree_to_script(tree, "load_json_output.py", "load_json_graph.png")


if __name__ == "__main__":
    main()
