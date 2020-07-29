import inspect
from typing import Optional, Type

from arcor2.clients import persistent_storage as storage
from arcor2.data.object_type import Models, ObjectType
from arcor2.exceptions import Arcor2Exception
from arcor2.helpers import ImportClsException, import_cls
from arcor2.object_types.abstract import Generic, GenericWithPose
from arcor2.source.object_types import check_object_type


class UploadException(Arcor2Exception):
    pass


def upload_def(type_def: Type[Generic], model: Optional[Models] = None) -> None:

    if not issubclass(type_def, GenericWithPose) and model:
        raise UploadException("Object without pose can't have collision model.")

    path = inspect.getfile(type_def)

    with open(path, "r") as source_file:

        source = source_file.read()

        try:
            check_object_type(type_def)
        except Arcor2Exception as e:
            print(e)
            raise UploadException(f"There is something wrong with source code of '{type_def.__name__}'.")

        obj_type = ObjectType(id=type_def.__name__, source=source, desc=type_def.description())

        if model:
            obj_type.model = model.metamodel()
            storage.put_model(model)

        print(f"Storing '{obj_type.id}'...")
        storage.update_object_type(obj_type)


def upload(module_cls: str, model: Optional[Models] = None) -> None:
    try:
        _, cls = import_cls(module_cls)
    except ImportClsException as e:
        raise UploadException(e)

    if not issubclass(cls, Generic):
        raise UploadException("Object should be derived from Generic.")

    upload_def(cls, model)
