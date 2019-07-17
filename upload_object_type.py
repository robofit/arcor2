#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from pymongo import MongoClient  # type: ignore
import sys
import importlib
import inspect
from arcor2.object_types import Generic
from arcor2.generate_source import check_object_type, GenerateSourceException
from arcor2.helpers import import_cls, ImportClsException


class UploadException(Exception):
    pass


def upload(module_cls: str):

    try:
        _, cls = import_cls(module_cls)
    except ImportClsException as e:
        raise UploadException(e)

    if not issubclass(cls, Generic):
        raise UploadException(f"'{cls.__name__}' not derived from 'Generic' object type.")

    path = inspect.getfile(cls)

    mongo = MongoClient()
    db = mongo.arcor2

    with open(path, "r") as source_file:

        source = source_file.read()

        try:
            check_object_type(source)
        except GenerateSourceException as e:
            print(e)
            raise UploadException(f"There is something wrong with source code of '{cls.__name__}'.")

        print(f"Storing '{cls.__name__}'...")
        # TODO check if it already exists?
        db.object_types.update_one({"_id": cls.__name__}, {'$set': {"source": source}}, upsert=True)


def main():

    try:
        arg = sys.argv[1]
    except IndexError:
        print("Usage: upload_object_type.py package.module/Cls")
        return

    try:
        upload(arg)
    except UploadException as e:
        print(e)
        return
    print('Done')


if __name__ == "__main__":
    main()
