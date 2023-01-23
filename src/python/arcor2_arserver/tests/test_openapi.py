from subprocess import check_output

import yaml
from openapi_spec_validator import validate_spec


def test_arserver_openapi() -> None:

    validate_spec(
        yaml.full_load(check_output(["python", "src.python.arcor2_arserver.scripts/arserver.pex", "--openapi"]))
    )
