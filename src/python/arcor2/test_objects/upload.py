#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from arcor2.data.object_type import Box as BoxModel
from arcor2.object_types.upload import upload_def
from arcor2.test_objects.box import Box
from arcor2.test_objects.box2 import Box2
from arcor2.test_objects.param_to_return import ParamToReturn
from arcor2.test_objects.tester import Tester


def main() -> None:

    upload_def(Box, BoxModel("Box", 0.1, 0.1, 0.1))
    upload_def(Box2, BoxModel("Box2", 0.2, 0.2, 0.2))
    upload_def(Tester, BoxModel("Tester", 0.3, 0.3, 0.3))
    upload_def(ParamToReturn)


if __name__ == "__main__":
    main()
