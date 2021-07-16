import os
import zipfile
from io import BytesIO
from typing import List, NamedTuple, Optional, Type

from arcor2.clients import project_service as ps
from arcor2.data.object_type import Mesh, Models, ObjectType
from arcor2.exceptions import Arcor2Exception
from arcor2.object_types.abstract import Generic, GenericWithPose, Robot
from arcor2.object_types.utils import check_object_type, get_containing_module_sources


class UploadException(Arcor2Exception):
    pass


class Urdf(NamedTuple):

    path_to_directory: str  # path to a URDF package directory
    archive_name: str  # resulting archive name


def upload_whatever(type_def: Type[object]) -> None:

    obj_type = ObjectType(id=type_def.__name__, source=get_containing_module_sources(type_def))
    print(f"Storing '{obj_type.id}'...")
    ps.update_object_type(obj_type)


def upload_def(
    type_def: Type[Generic],
    model: Optional[Models] = None,
    urdf: Optional[Urdf] = None,
    file_to_upload: Optional[str] = None,
) -> None:
    """Uploads ObjectType definition to the Project service.

    :param type_def: Class definition.
    :param model: Collision model.
    :param urdf: If the type is robot, path to its URDF can be given here.
    :param file_to_upload: Path to a file. Used e.g. to upload a mesh together with the ObjectType.
    :return:
    """

    if not issubclass(type_def, GenericWithPose) and model:
        raise UploadException("Object without pose can't have collision model.")

    if not issubclass(type_def, Robot) and urdf:
        raise UploadException("Parameter urdf set for non-Robot.")

    if issubclass(type_def, Robot) and model:
        raise UploadException("Parameter 'model' should not be set for robots.")

    try:
        check_object_type(type_def)
    except Arcor2Exception as e:
        raise UploadException(f"{type_def.__name__} is not a valid ObjectType. {str(e)}")

    obj_type = ObjectType(
        id=type_def.__name__, source=get_containing_module_sources(type_def), description=type_def.description()
    )

    if issubclass(type_def, GenericWithPose) and model:

        if not type_def.mesh_filename:
            raise UploadException("Mesh filename not set.")

        if model.id != obj_type.id:
            raise UploadException("Model id have to be the same as ObjectType id.")

        obj_type.model = model.metamodel()

        if isinstance(model, Mesh):
            if not file_to_upload:
                raise UploadException("For mesh collision model, file_to_upload parameter have to be set.")

            try:
                with open(file_to_upload, "rb") as f:
                    ps.upload_file(type_def.mesh_filename, f.read())
            except OSError as e:
                raise UploadException(f"Failed to read mesh file. {str(e)}")

        ps.put_model(model)

    print(f"Storing '{obj_type.id}'...")
    ps.update_object_type(obj_type)

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
        ps.upload_file(urdf.archive_name, mem_zip.getvalue())
