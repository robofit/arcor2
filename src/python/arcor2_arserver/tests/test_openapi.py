import os
import tempfile
from subprocess import check_output

import yaml
from openapi_spec_validator import validate_spec


def test_arserver_openapi() -> None:

    with tempfile.TemporaryDirectory() as tmp:

        my_env = os.environ.copy()
        my_env["ARCOR2_DATA_PATH"] = tmp

        validate_spec(
            yaml.full_load(check_output(["./src.python.arcor2_arserver.scripts/arserver.pex", "--openapi"], env=my_env))
        )
