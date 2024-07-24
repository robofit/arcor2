import os
from subprocess import check_output

import yaml
from openapi_spec_validator import validate


def test_openapi() -> None:
    my_env = os.environ.copy()
    my_env["AMENT_PREFIX_PATH"] = "/opt/ros/jazzy"
    my_env["PEX_EXTRA_SYS_PATH"] = "/opt/ros/jazzy/lib/python3.12/site-packages"

    validate(yaml.full_load(check_output(["python", "src.python.arcor2_ur.scripts/ur.pex", "--swagger"], env=my_env)))
