import json
import logging
import traceback
from dataclasses import dataclass, field
from typing import Optional, Type, TypeAlias, Union, cast

from apispec import APISpec
from apispec_webframeworks.flask import FlaskPlugin
from dataclasses_jsonschema import DEFAULT_SCHEMA_TYPE, FieldMeta, JsonSchemaMixin
from dataclasses_jsonschema.apispec import DataclassesPlugin
from flask import Flask, Response, jsonify
from flask_cors import CORS
from flask_swagger_ui import get_swaggerui_blueprint

from arcor2 import __name__ as package_name
from arcor2 import env
from arcor2.data.common import WebApiError as IWebApiError
from arcor2.exceptions import Arcor2Exception

# TODO mypy likes Union here :-/
RespT: TypeAlias = Union[Response, tuple[str, int], tuple[Response, int]]  # noqa:NU001


debug = env.get_bool("ARCOR2_FLASK_DEBUG")


class FlaskException(Arcor2Exception):
    """Service should get WebApiError class and pass it to swagger
    generator."""

    service: str
    description: str

    def __init__(self, message: str, content: None | str = None):
        super().__init__(message)
        self.content = content

    @property
    def type(self):  # Use class.__name__ to get type when dealing with class objects
        return self.__class__.__name__

    def to_dict(self) -> dict:
        return IWebApiError(self.service, str(self), self.type, self.description, self.content).to_dict()


class General(FlaskException):
    service = package_name
    description = "Occurs when exception has no additional information or is unexpected."


class WebApiErrorFactory:
    """Build concrete web api schema class with correct fields description."""

    @staticmethod
    def _get_error_type_table(*allowed_exceptions: Type[FlaskException]) -> str:
        return "| Error type | Description |\n| --- | --- |\n" + "\n".join(
            [f"| {e.__name__} | {e.description} |" for e in allowed_exceptions]
        )

    @classmethod
    def get_class(cls, *allowed_exceptions: Type[FlaskException]) -> Type[IWebApiError]:
        # add general error to allowed for all services (this way it will appear in swagger)
        allowed_exceptions = (General, *allowed_exceptions)

        @dataclass
        class WebApiError(JsonSchemaMixin):
            """Represents any Web API error."""

            service: str = field(
                metadata=FieldMeta(
                    schema_type=DEFAULT_SCHEMA_TYPE,
                    description="Gets the service name where error occurred.",
                ).as_dict
            )

            message: str = field(
                metadata=FieldMeta(
                    schema_type=DEFAULT_SCHEMA_TYPE,
                    description="Gets human-readable explanation specific to this occurrence of the problem.",
                ).as_dict
            )

            type: str = field(
                metadata=FieldMeta(
                    schema_type=DEFAULT_SCHEMA_TYPE,
                    description=(
                        f"Gets application specific error type.\n\n" f"{cls._get_error_type_table(*allowed_exceptions)}"
                    ),
                ).as_dict
            )

            description: str = field(
                metadata=FieldMeta(
                    schema_type=DEFAULT_SCHEMA_TYPE,
                    description="Gets short, human-readable description of the application specific type.",
                ).as_dict
            )

            # This property should be parsed as JSON and validated against some model.
            # Validation and parsing should be handled by information consumer.
            # Model could be obtained from `type` property description.
            content: Optional[str] = field(
                metadata=FieldMeta(
                    schema_type=DEFAULT_SCHEMA_TYPE,
                    description=(
                        "Gets specific JSON object to this occurrence of the problem. "
                        "The data model is specific to the type "
                        "and should be documented on each API method."
                    ),
                    default=None,
                ).as_dict
            )

        return cast(Type[IWebApiError], WebApiError)


def create_app(import_name: str) -> Flask:
    app = Flask(import_name)
    CORS(app)
    return app


def run_app(
    app: Flask,
    name: str,
    version: str,
    port: int,
    dataclasses: None | list[type[JsonSchemaMixin]] = None,
    print_spec: bool = False,
    dependencies: None | dict[str, str] = None,
    *,
    api_version: None | str = None,
) -> None:
    if not api_version:
        api_version = version

    spec = APISpec(
        title=name,
        version=api_version,
        openapi_version="3.0.2",
        plugins=[FlaskPlugin(), DataclassesPlugin()],
        info={
            "description": "Dependencies: none"
            if dependencies is None
            else f'Dependencies: {", ".join([f"{k} {v}" for k, v in dependencies.items()])}'
        },
    )

    if dataclasses is not None:
        for dc in dataclasses:
            spec.components.schema(dc.__name__, schema=dc)

    with app.test_request_context():
        for rule in app.url_map.iter_rules():
            if rule.endpoint != "static":
                spec.path(view=app.view_functions[rule.endpoint])

    if print_spec:
        print(spec.to_yaml())
        return

    @app.route("/healthz/ready")
    def health():
        return Response(status=200)

    @app.route("/swagger/api/swagger.json", methods=["GET"])
    def get_swagger() -> RespT:
        return jsonify(spec.to_dict())

    @app.errorhandler(Arcor2Exception)
    def handle_bad_request_general(e: Arcor2Exception) -> tuple[str, int]:
        if debug:
            print("".join(traceback.format_exception(None, e, e.__traceback__)))
        return json.dumps(General(str(e)).to_dict()), 500

    @app.errorhandler(FlaskException)
    def handle_bad_request_intentional(e: FlaskException) -> tuple[str, int]:
        if debug:
            print("".join(traceback.format_exception(None, e, e.__traceback__)))
        return json.dumps(e.to_dict()), 500

    SWAGGER_URL = "/swagger"

    swaggerui_blueprint = get_swaggerui_blueprint(
        SWAGGER_URL, "./api/swagger.json"  # Swagger UI static files will be mapped to '{SWAGGER_URL}/dist/'
    )

    # Register blueprint at URL
    app.register_blueprint(swaggerui_blueprint, url_prefix=SWAGGER_URL)

    if not env.get_bool("ARCOR2_REST_API_DEBUG", False):
        # turn off logging each endpoint call by default
        log = logging.getLogger("werkzeug")
        log.setLevel(logging.ERROR)

    app.run(host="0.0.0.0", port=port)
