import importlib
import sys
from typing import Iterator

import pytest


@pytest.fixture
def service_client(tmp_path) -> Iterator:
    # ensure fresh module graph for each test so DB path is picked up from env
    db_path = tmp_path / "project.sqlite"

    for mod in list(sys.modules):
        if mod.startswith("arcor2_storage"):
            sys.modules.pop(mod)

    import os

    os.environ["ARCOR2_STORAGE_DB_PATH"] = str(db_path)

    import arcor2_storage.scripts.storage as service

    importlib.reload(service)

    with service.app.test_client() as client:
        yield client
