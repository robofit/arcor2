import json
import logging
from typing import List, Optional, Tuple, Type, Union

from apispec import APISpec
from apispec_webframeworks.flask import FlaskPlugin
from dataclasses_jsonschema import JsonSchemaMixin
from dataclasses_jsonschema.apispec import DataclassesPlugin
from flask import Flask, Response, jsonify
from flask_cors import CORS
from flask_swagger_ui import get_swaggerui_blueprint

from arcor2 import env
from arcor2.exceptions import Arcor2Exception

RespT = Union[Response, Tuple[str, int], Tuple[Response, int]]


class FlaskException(Arcor2Exception):
    def __init__(self, *args, error_code: int):
        super().__init__(*args)
        self.error_code = error_code


def create_app(import_name: str) -> Flask:

    app = Flask(import_name)
    CORS(app)
    return app


def run_app(
    app: Flask,
    name: str,
    version: str,
    api_version: str,
    port: int,
    dataclasses: Optional[List[Type[JsonSchemaMixin]]] = None,
    print_spec: bool = False,
) -> None:

    spec = APISpec(
        title=f"{name} ({version})",
        version=api_version,
        openapi_version="3.0.2",
        plugins=[FlaskPlugin(), DataclassesPlugin()],
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

    @app.route("/swagger/api/swagger.json", methods=["GET"])
    def get_swagger() -> RespT:
        return jsonify(spec.to_dict())

    @app.errorhandler(Arcor2Exception)  # type: ignore  # TODO what's wrong?
    def handle_bad_request_general(e: Arcor2Exception) -> Tuple[str, int]:
        return json.dumps(str(e)), 400

    @app.errorhandler(FlaskException)  # type: ignore  # TODO what's wrong?
    def handle_bad_request_intentional(e: FlaskException) -> Tuple[str, int]:
        return json.dumps(str(e)), e.error_code

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
