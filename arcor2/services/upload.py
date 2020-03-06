import inspect
from typing import Type

from arcor2.source.services import check_service_type
from arcor2.source import SourceException
from arcor2.helpers import import_cls, ImportClsException
from arcor2.exceptions import Arcor2Exception
from arcor2 import persistent_storage as storage
from arcor2.data.services import ServiceType
from arcor2.services import Service


class UploadException(Arcor2Exception):
    pass


def upload_cls(cls: Type[Service]) -> None:

    path = inspect.getfile(cls)

    with open(path, "r") as source_file:

        source = source_file.read()

        try:
            check_service_type(source, cls.__name__)
        except SourceException as e:
            print(e)
            raise UploadException(f"There is something wrong with source code of '{cls.__name__}'.")

        srv_type = ServiceType(id=cls.__name__, source=source, desc=cls.description())

        print(f"Storing '{srv_type.id}'...")
        storage.update_service_type(srv_type)


def upload(module_cls: str) -> None:

    try:
        _, cls = import_cls(module_cls)
    except ImportClsException as e:
        raise UploadException(e)

    if not issubclass(cls, Service):
        print("Not subclass of Service!")
        return

    upload_cls(cls)
