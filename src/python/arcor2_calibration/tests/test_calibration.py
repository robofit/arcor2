from subprocess import check_output

import yaml

from arcor2_web.testing.openapi import assert_valid_openapi_spec


def test_openapi() -> None:
    spec = yaml.full_load(
        check_output(["python", "src.python.arcor2_calibration.scripts/calibration.pex", "--swagger"])
    )
    assert_valid_openapi_spec(spec)
