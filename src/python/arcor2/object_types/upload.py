import os
import zipfile
from io import BytesIO
from typing import NamedTuple

from arcor2.clients import asset
from arcor2.clients import project_service as ps
from arcor2.data.object_type import Mesh, Models, ObjectType
from arcor2.exceptions import Arcor2Exception
from arcor2.object_types.abstract import CollisionObject, Generic, Robot
from arcor2.object_types.utils import check_object_type, get_containing_module_sources


class UploadException(Arcor2Exception):
    pass


class Urdf(NamedTuple):

    path_to_directory: str  # path to a URDF package directory
    archive_name: str  # resulting archive name


def upload_whatever(type_def: type[object]) -> None:

    obj_type = ObjectType(id=type_def.__name__, source=get_containing_module_sources(type_def))
    print(f"Storing '{obj_type.id}'...")
    ps.update_object_type(obj_type)


def upload_def(
    type_def: type[Generic],
    model: None | Models = None,
    urdf: None | Urdf = None,
    file_to_upload: None | str = None,
) -> None:
    """Uploads ObjectType definition to the Project service.

    :param type_def: Class definition.
    :param model: Collision model.
    :param urdf: If the type is robot, path to its URDF can be given here.
    :param file_to_upload: Path to a file. Used e.g. to upload a mesh together with the ObjectType.
    :return:
    """

    if not issubclass(type_def, Robot) and urdf:
        raise UploadException("Parameter 'urdf' set for non-Robot.")

    try:
        check_object_type(type_def)
    except Arcor2Exception as e:
        raise UploadException(f"{type_def.__name__} is not a valid ObjectType. {str(e)}")

    obj_type = ObjectType(
        id=type_def.__name__, source=get_containing_module_sources(type_def), description=type_def.description()
    )

    if issubclass(type_def, CollisionObject):
        if not model:
            raise UploadException("Parameter 'model' must be set for CollisionObject.")

        if model.id != obj_type.id:
            raise UploadException("Model id have to be the same as ObjectType id.")

        obj_type.model = model.metamodel()

        if isinstance(model, Mesh):

            if not type_def.mesh_filename:
                raise UploadException("Mesh filename not set.")

            if not file_to_upload:
                raise UploadException("For mesh collision model, file_to_upload parameter have to be set.")

            try:
                with open(file_to_upload, "rb") as f:
                    asset.create_asset(
                        type_def.mesh_filename,
                        f.read(),
                        directory_path="/meshes",
                        description=f"mesh for {obj_type.id}",
                    )
            except OSError as e:
                raise UploadException(f"Failed to read mesh file. {str(e)}")

        ps.put_model(model)

    else:
        if model:
            raise UploadException("Parameter 'model' set for non-CollisionObject.")

    if urdf:

        if not os.path.isdir(urdf.path_to_directory):
            print(f"{urdf.path_to_directory} is not a directory.")
            return

        print(f"Storing URDF package for '{obj_type.id}'.")

        paths: list[str] = []

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
        asset.create_asset(
            urdf.archive_name,
            mem_zip.getvalue(),
            directory_path="/urdf_packages",
            description=f"URDF for {obj_type.id}",
        )

    print(f"Storing '{obj_type.id}'...")
    ps.update_object_type(obj_type)
