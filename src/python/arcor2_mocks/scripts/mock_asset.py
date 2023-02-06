#!/usr/bin/env python3

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
from io import BytesIO

import fastuuid as uuid
import humps
from flask import jsonify, request

from arcor2.clients.asset import AssetInfo
from arcor2.flask import Response, RespT, create_app, run_app
from arcor2.json import JsonType
from arcor2_mocks import ASSET_PORT, ASSET_SERVICE_NAME, version
from arcor2_mocks.exceptions_asset import Argument, NotFound, WebApiError


@dataclass
class Asset:
    info: AssetInfo
    file: BytesIO


app = create_app(__name__)

ASSETS: dict[str, Asset] = {}


# ----------------------------------------------------------------------------------------------------------------------

# TODO dependencies and tags parameters omitted as not really needed at the moment
@app.route("/assets", methods=["POST"])
def post_asset() -> RespT:
    """Creates the asset.
    ---
    post:
        tags:
            - Assets
        description: Creates the asset.
        parameters:
            - name: id
              in: query
              description: The unique identification of the asset.
              required: false
              schema:
                type: string
            - name: directoryPath
              in: query
              description: The path to a directory where the asset will be stored.
              required: false
              schema:
                type: string
            - name: description
              in: query
              description: A short text that describes the meaning of the asset.
              required: false
              schema:
                type: string
            - name: type
              in: query
              description: The type of the asset.
              required: false
              schema:
                type: string
        requestBody:
              content:
                multipart/form-data:
                  schema:
                    type: object
                    required:
                        - assetData
                    properties:
                      assetData:
                        type: string
                        format: binary
        responses:
            200:
              description: Timestamp of last project modification.
              content:
                application/json:
                  schema:
                    $ref: AssetInfo
            500:
              description: "Error types: **Argument**, **AssetSystem**, **AssetReference**"
              content:
                application/json:
                  schema:
                    $ref: WebApiError
    """

    asset_id = request.args.get("id", default=None)
    asset_type = request.args.get("type", default="unknown")
    directory_path = request.args.get("directoryPath", default=None)
    description = request.args.get("description", default=None)

    if not asset_id:
        asset_id = uuid.uuid4().hex

    assert asset_id

    buff = BytesIO()
    fs = request.files["assetData"]
    fs.save(buff)

    if asset_id in ASSETS:
        raise Argument(f"Asset with id {asset_id} already exists.")

    now = datetime.now(tz=timezone.utc)
    asset_info = AssetInfo(
        asset_id, asset_type, now, now, file_name=fs.filename, directory_path=directory_path, description=description
    )

    ASSETS[asset_id] = Asset(asset_info, buff)

    return jsonify(humps.camelize(asset_info.to_dict()))


# TODO filters omitted for simplicity
@app.route("/assets/info", methods=["GET"])
def get_assets() -> RespT:
    """Get information about all assets that meet given filters.
    ---
    get:
        tags:
        - Assets
        summary: Get information about all assets that meet given filters.
        responses:
            200:
              description: Success
              content:
                application/json:
                  schema:
                    type: array
                    items:
                      $ref: AssetInfo
            500:
              description: "Error types: **General**."
              content:
                application/json:
                  schema:
                    $ref: WebApiError
    """

    ret: list[JsonType] = []

    for asset in ASSETS.values():
        ret.append(humps.camelize(asset.info.to_dict()))

    return jsonify(ret)


@app.route("/assets/<string:id>/exists", methods=["GET"])
def get_exists(id: str) -> RespT:
    """Test if asset exists.
    ---
    get:
        description: Test if asset exists.
        tags:
           - Assets
        parameters:
            - name: id
              in: path
              description: The unique identification of the asset.
              required: false
              schema:
                type: string
        responses:
            200:
              description: Ok
              content:
                application/json:
                    schema:
                        type: boolean
            500:
              description: "Error types: **General**, **StartError**."
              content:
                application/json:
                  schema:
                    $ref: WebApiError
    """

    return jsonify(id in ASSETS), 200


@app.route("/assets/<string:id>", methods=["DELETE"])
def delete_asset(id: str) -> RespT:
    """Deletes asset.
    ---
    delete:
        tags:
            - Asset
        summary: Deletes asset.
        parameters:
            - name: id
              in: path
              description: unique ID
              required: true
              schema:
                type: string
        responses:
            200:
              description: Ok
            500:
              description: "Error types: **General**, **NotFound**."
              content:
                application/json:
                  schema:
                    $ref: WebApiError
    """

    try:
        del ASSETS[id]
    except KeyError:
        raise NotFound("Asset not found.")

    return Response(status=200)


# ----------------------------------------------------------------------------------------------------------------------


def main() -> None:

    parser = argparse.ArgumentParser(description=ASSET_SERVICE_NAME)
    parser.add_argument("-s", "--swagger", action="store_true", default=False)
    args = parser.parse_args()

    run_app(
        app,
        ASSET_SERVICE_NAME,
        version(),
        ASSET_PORT,
        [
            AssetInfo,
            WebApiError,
        ],
        args.swagger,
        api_version="1.0.0",
    )


if __name__ == "__main__":
    main()
