import inspect

from pymongo import MongoClient  # type: ignore

from arcor2.object_types import Generic
from arcor2.source.object_types import check_object_type
from arcor2.source import SourceException
from arcor2.helpers import import_cls, ImportClsException
from arcor2.exceptions import Arcor2Exception


class UploadException(Arcor2Exception):
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
        except SourceException as e:
            print(e)
            raise UploadException(f"There is something wrong with source code of '{cls.__name__}'.")

        print(f"Storing '{cls.__name__}'...")
        # TODO check if it already exists?
        db.object_types.update_one({"id": cls.__name__}, {'$set': {"source": source}}, upsert=True)
