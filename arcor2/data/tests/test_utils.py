from openapi_spec_validator import validate_spec  # type: ignore
import yaml
from arcor2.data import utils


def test_swagger_models():
    validate_spec(yaml.full_load(utils.generate_swagger()))
