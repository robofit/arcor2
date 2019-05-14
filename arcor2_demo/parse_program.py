#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import ast
from astmonkey import visitors, transformers
import autopep8


def main():

    with open("pcb_tester_program.py", "r") as source:

        node = ast.parse(source.read())
        node = transformers.ParentChildNodeTransformer().visit(node)
        visitor = visitors.GraphNodeVisitor()
        visitor.visit(node)

        visitor.graph.write_png('graph.png')

        generated_code = visitors.to_source(node)

        generated_code = autopep8.fix_code(
            generated_code, options={'aggressive': 1})

        print(generated_code)


if __name__ == "__main__":
    main()
