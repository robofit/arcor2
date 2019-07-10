#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from pymongo import MongoClient  # type: ignore
import inspect

# TODO import those dynamically?
from box import Box
from tester import Tester
from box2 import Box2

"""
Just for testing purposes - until server/API will support creating object_types.
"""


def main():

    mongo = MongoClient()
    db = mongo.arcor2
    for cls in (Box, Tester, Box2):
        path = inspect.getmodule(cls).__file__

        with open(path, "r") as source:
            print(f"Storing '{cls.__name__}'...")
            db.object_types.update_one({"_id": cls.__name__}, {'$set': {"source": source.read()}}, upsert=True)

    print('Done')


if __name__ == "__main__":
    main()
