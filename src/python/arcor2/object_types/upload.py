import os
import zipfile
from io import BytesIO
from typing import List, NamedTuple, Optional, Type

from arcor2.clients import persistent_storage as storage
from arcor2.data.object_type import Models, ObjectType
from arcor2.exceptions import Arcor2Exception
from arcor2.object_types.abstract import Generic, GenericWithPose
from arcor2.object_types.utils import check_object_type, get_containing_module_sources


class UploadException(Arcor2Exception):
    pass


class Urdf(NamedTuple):

    path_to_directory: str
    archive_name: str


def upload_def(type_def: Type[Generic], model: Optional[Models] = None, urdf: Optional[Urdf] = None) -> None:

    if not issubclass(type_def, GenericWithPose) and model:
        raise UploadException("Object without pose can't have collision model.")

    try:
        check_object_type(type_def)
    except Arcor2Exception as e:
        print(e)
        raise UploadException(f"There is something wrong with source code of '{type_def.__name__}'.")

    obj_type = ObjectType(
        id=type_def.__name__, source=get_containing_module_sources(type_def), desc=type_def.description()
    )

    if model:
        obj_type.model = model.metamodel()
        storage.put_model(model)

    print(f"Storing '{obj_type.id}'...")
    storage.update_object_type(obj_type)

    if urdf:

        if not os.path.isdir(urdf.path_to_directory):
            print(f"{urdf.path_to_directory} is not a directory.")
            return

        print(f"Storing URDF package for '{obj_type.id}'.")

        paths: List[str] = []

        # full path is in form src/python/arcor2_fit_demo/data/dobot-m1/dobot_m1_description/meshes
        # so we need to remove the prefix (e.g. src/python/arcor2_fit_demo/data/dobot-m1)
        # let's find the prefix...
        for root, _, files in os.walk(urdf.path_to_directory):
            for filename in files:
                paths.append(os.path.join(root, filename))

        prefix = os.path.commonpath(paths)

        mem_zip = BytesIO()
        with zipfile.ZipFile(mem_zip, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
            for root, _, files in os.walk(urdf.path_to_directory):
                for filename in files:
                    path = os.path.join(root, filename)
                    # in the archive, the path will be without the prefix
                    zf.write(path, os.path.relpath(path, prefix))

        mem_zip.seek(0)
        storage.upload_mesh_file(urdf.archive_name, mem_zip.getvalue())
