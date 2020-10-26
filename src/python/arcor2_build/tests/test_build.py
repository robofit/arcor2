from subprocess import check_output

import yaml
from openapi_spec_validator import validate_spec  # type: ignore


def test_build_openapi() -> None:
    validate_spec(yaml.full_load(check_output(["./src.python.arcor2_build.scripts/build.pex", "--swagger"])))
