import os
import sys


try:
    PROJECT_PATH = os.environ["ARCOR2_PROJECT_PATH"]
except KeyError:
    sys.exit("'ARCOR2_PROJECT_PATH' env. variable not set.")

CLEANUP_SERVICES: bool = os.getenv("ARCOR2_CLEANUP_SERVICES", "True") == "True"
