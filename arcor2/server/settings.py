import os
import sys

try:
    DATA_PATH = os.environ["ARCOR2_DATA_PATH"]
except KeyError:
    sys.exit("'ARCOR2_DATA_PATH' env. variable not set.")

URDF_PATH = os.path.join(DATA_PATH, "urdf")
