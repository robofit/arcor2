from subprocess import check_output

from openapi_spec_validator import validate_spec  # type: ignore

import yaml


def test_build_openapi() -> None:
    validate_spec(yaml.full_load(check_output(["arcor2_build", "--swagger"])))
