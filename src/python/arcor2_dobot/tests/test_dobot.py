from subprocess import check_output

import yaml
from openapi_spec_validator import validate_spec


def test_dobot_openapi() -> None:
    validate_spec(yaml.full_load(check_output(["python", "src.python.arcor2_dobot.scripts/dobot.pex", "--swagger"])))
