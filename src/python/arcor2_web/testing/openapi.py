from openapi_spec_validator import validate_spec


def assert_valid_openapi_spec(spec: dict) -> None:
    validate_spec(spec)
    assert spec.get("paths"), "OpenAPI spec must define at least one path."
