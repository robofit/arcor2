import io
import os
import tempfile
import zipfile

from urdfpy import URDF

from arcor2 import rest
from arcor2.exceptions import Arcor2Exception


class Arcor2UrdfException(Arcor2Exception):
    pass


def is_urdf_file(fname: str) -> bool:

    _, ext = os.path.splitext(fname)
    return ext in (".urdf", ".xml")


def urdf_from_path(path_to_urdf: str) -> URDF:

    for file in os.listdir(path_to_urdf):
        if is_urdf_file(file):
            with open(os.path.join(path_to_urdf, file)) as f:
                s = f.read()
            break
    else:
        raise Arcor2UrdfException("Failed to find urdf file.")

    s = s.replace("package://", "")

    buff = io.BytesIO(s.encode())
    buff.name = os.path.join(path_to_urdf, file)

    try:
        return URDF.load(buff)
    except (ValueError, TypeError) as e:
        raise Arcor2UrdfException(str(e)) from e


def urdf_from_url(url_of_zipped_package: str) -> URDF:

    with tempfile.TemporaryDirectory() as tmp_dir:
        path_to_zip = os.path.join(tmp_dir, "urdf.zip")
        rest.download(url_of_zipped_package, path_to_zip)

        with zipfile.ZipFile(path_to_zip, "r") as zip_ref:
            zip_ref.extractall(tmp_dir)

        return urdf_from_path(tmp_dir)
