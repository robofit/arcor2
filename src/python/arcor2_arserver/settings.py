import os
import sys
import tempfile

try:
    DATA_PATH = os.environ["ARCOR2_DATA_PATH"]
except KeyError:
    sys.exit("'ARCOR2_DATA_PATH' env. variable not set.")

URDF_PATH = os.path.join(DATA_PATH, "urdf")

OBJECT_TYPE_PATH = tempfile.mkdtemp()
OBJECT_TYPE_MODULE = "arcor2_object_types"
