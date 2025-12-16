import os
import tempfile
from subprocess import check_output

import yaml

from arcor2_web.testing.openapi import assert_valid_openapi_spec


def test_storage_openapi() -> None:
    with tempfile.TemporaryDirectory() as tmp_dir:
        env = os.environ.copy()
        env["ARCOR2_STORAGE_DB_PATH"] = os.path.join(tmp_dir, "arcor2_storage.sqlite")
        spec = yaml.full_load(
            check_output(["python", "src.python.arcor2_storage.scripts/storage.pex", "--swagger"], env=env)
        )
    assert_valid_openapi_spec(spec)
