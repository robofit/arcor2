import os
import tempfile
from subprocess import check_output

import yaml
from openapi_spec_validator import validate_spec


def test_execution_proxy_openapi() -> None:

    with tempfile.TemporaryDirectory() as tmp_dir:

        my_env = os.environ.copy()
        my_env["ARCOR2_PROJECT_PATH"] = tmp_dir

        validate_spec(
            yaml.full_load(
                check_output(
                    ["python", "src.python.arcor2_execution_rest_proxy.scripts/execution_rest_proxy.pex", "--swagger"],
                    env=my_env,
                )
            )
        )
