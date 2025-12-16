import os
from subprocess import check_output

import yaml

from arcor2_web.testing.openapi import assert_valid_openapi_spec


def test_build_openapi() -> None:
    my_env = os.environ.copy()
    my_env["ARCOR2_PROJECT_PATH"] = ""

    cmd = ["python", "src.python.arcor2_build.scripts/build.pex", "--swagger"]
    spec = yaml.full_load(check_output(cmd, env=my_env))
    assert_valid_openapi_spec(spec)
