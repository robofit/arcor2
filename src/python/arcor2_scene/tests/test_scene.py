from subprocess import check_output

import yaml

from arcor2_web.testing.openapi import assert_valid_openapi_spec


def test_project_mock_openapi() -> None:
    spec = yaml.full_load(check_output(["python", "src.python.arcor2_scene.scripts/scene.pex", "--swagger"]))
    assert_valid_openapi_spec(spec)
