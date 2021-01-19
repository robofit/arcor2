from typing import List, Optional, Tuple, Type, Union

from apispec import APISpec
from apispec_webframeworks.flask import FlaskPlugin
from dataclasses_jsonschema import JsonSchemaMixin
from dataclasses_jsonschema.apispec import DataclassesPlugin
from flask import Flask, Response, jsonify
from flask_cors import CORS
from flask_swagger_ui import get_swaggerui_blueprint

from arcor2.exceptions import Arcor2Exception

RespT = Union[Response, Tuple[str, int]]


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
    def get_swagger() -> str:
        return jsonify(spec.to_dict())

    @app.errorhandler(Arcor2Exception)
    def handle_bad_request(e: Arcor2Exception) -> Tuple[str, int]:
        return str(e), 400

    SWAGGER_URL = "/swagger"

    swaggerui_blueprint = get_swaggerui_blueprint(
        SWAGGER_URL, "./api/swagger.json"  # Swagger UI static files will be mapped to '{SWAGGER_URL}/dist/'
    )

    # Register blueprint at URL
    app.register_blueprint(swaggerui_blueprint, url_prefix=SWAGGER_URL)

    app.run(host="0.0.0.0", port=port)
