import collections
import fractions
import io
import math
import os
import tempfile
import zipfile

from arcor2 import rest
from arcor2.exceptions import Arcor2Exception

# this is a workaround to make urdfpy/networkx happy under Python 3.9/3.10
# TODO not sure if it really works in runtime, the best would be to solve https://github.com/mmatl/urdfpy/issues/4
# or to switch to another package as proposed here https://github.com/robofit/arcor2/issues/706
fractions.gcd = math.gcd  # type: ignore

# another workaround related to urdfpy/networkx and Python 3.10
from collections.abc import Iterable, Mapping, Set  # noqa:E402

collections.Mapping = Mapping  # type: ignore
collections.Set = Set  # type: ignore
collections.Iterable = Iterable  # type: ignore

from urdfpy import URDF  # noqa


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
