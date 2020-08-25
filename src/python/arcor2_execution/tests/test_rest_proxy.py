from subprocess import check_output

import pytest  # type: ignore
import yaml
from openapi_spec_validator import validate_spec  # type: ignore


@pytest.mark.skip(reason="Integration tests are temporarily disabled.")
def test_execution_proxy_openapi() -> None:
    validate_spec(yaml.full_load(check_output(["arcor2_execution_rest_proxy", "--swagger"])))
