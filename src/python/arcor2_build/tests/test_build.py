import os
from subprocess import check_output

import yaml
from openapi_spec_validator import validate_spec


def test_build_openapi() -> None:
    my_env = os.environ.copy()
    my_env["ARCOR2_PROJECT_PATH"] = ""

    validate_spec(
        yaml.full_load(check_output(["python", "src.python.arcor2_build.scripts/build.pex", "--swagger"], env=my_env))
    )
