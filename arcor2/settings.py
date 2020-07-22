import os
import sys

PROJECT_PATH_NAME = "ARCOR2_PROJECT_PATH"
CLEANUP_SERVICES_NAME = "ARCOR2_CLEANUP_SERVICES"

try:
    PROJECT_PATH = os.environ[PROJECT_PATH_NAME]
except KeyError:
    sys.exit(f"'{PROJECT_PATH_NAME}' env. variable not set.")
