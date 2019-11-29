import inspect
from typing import Optional

from arcor2.source.object_types import check_object_type
from arcor2.source import SourceException
from arcor2.helpers import import_cls, ImportClsException
from arcor2.exceptions import Arcor2Exception
from arcor2 import persistent_storage as storage
from arcor2.data.object_type import ObjectType, Models
from arcor2.object_types import Generic


class UploadException(Arcor2Exception):
    pass


def upload(module_cls: str, model: Optional[Models] = None) -> None:

    try:
        _, cls = import_cls(module_cls)
    except ImportClsException as e:
        raise UploadException(e)

    path = inspect.getfile(cls)

    with open(path, "r") as source_file:

        source = source_file.read()

        try:
            check_object_type(source, cls.__name__)
        except SourceException as e:
            print(e)
            raise UploadException(f"There is something wrong with source code of '{cls.__name__}'.")

        assert issubclass(cls, Generic)

        obj_type = ObjectType(id=cls.__name__, source=source, desc=cls.description())

        if model:
            obj_type.model = model.metamodel()
            storage.put_model(model)

        print(f"Storing '{obj_type.id}'...")
        storage.update_object_type(obj_type)
