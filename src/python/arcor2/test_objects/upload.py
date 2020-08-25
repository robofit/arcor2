#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from arcor2.data.object_type import Box
from arcor2.object_types.upload import upload


def main() -> None:

    upload("arcor2.test_objects/Box", Box("Box", 0.1, 0.1, 0.1))
    upload("arcor2.test_objects/Box2", Box("Box2", 0.2, 0.2, 0.2))
    upload("arcor2.test_objects/Tester", Box("Tester", 0.3, 0.3, 0.3))


if __name__ == "__main__":
    main()
