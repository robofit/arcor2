from subprocess import check_output

import pytest  # type: ignore
import yaml
from openapi_spec_validator import validate_spec  # type: ignore


@pytest.mark.skip(reason="Integration tests are temporarily disabled.")
def test_project_mock_openapi() -> None:
    validate_spec(yaml.full_load(check_output(["arcor2_scene_mock", "--swagger"])))
