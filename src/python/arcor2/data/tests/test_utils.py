import yaml
from openapi_spec_validator import validate_spec  # type: ignore

import arcor2
import arcor2.data.common
import arcor2.data.events
import arcor2.data.object_type
from arcor2.data import rpc, utils


def test_swagger_models() -> None:
    validate_spec(
        yaml.full_load(
            utils.generate_swagger(
                "ARCOR2",
                arcor2.version(),
                (arcor2.data.common, arcor2.data.object_type, rpc.common, arcor2.data.events),
            )
        )
    )
