import os
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from dataclasses_jsonschema import JsonSchemaMixin
from dataclasses_jsonschema.type_defs import Nullable

from arcor2 import rest

URL = os.getenv("ARCOR2_ASSET_SERVICE_URL", "http://0.0.0.0:10040")


@dataclass
class AssetInfo(JsonSchemaMixin):
    id: str
    type: str
    created: datetime
    modified: datetime
    file_path: Optional[str] = None
    file_name: Optional[str] = None
    name: Optional[str] = None
    extension: Optional[str] = None
    directory_path: Optional[str] = None
    description: Nullable[str | None] = None
    tags: Optional[list[str]] = None
    dependencies: Optional[list[str]] = None


def asset_info() -> list[AssetInfo]:
    return rest.call(rest.Method.GET, f"{URL}/assets/info", list_return_type=AssetInfo)


def asset_ids() -> set[str]:
    return {ai.id for ai in asset_info()}


def create_asset(
    id: str,  # on Asset service, id is not required but for arcor2, it makes more sense to require it
    asset_data: bytes,
    *,
    directory_path: str | None = None,
    description: str | None = None,
    type: str | None = None,
    dependencies: list[str] | None = None,
    tags: list[str] | None = None,
    upsert: bool = True,
) -> AssetInfo:
    """Creates the asset."""

    if upsert and asset_exists(id):
        delete_asset(id, remove_dependents=True)

    return rest.call(
        rest.Method.POST,
        f"{URL}/assets",
        params={
            "id": id,
            "directory_path": directory_path,
            "description": description,
            "type": type,
            "dependencies": dependencies,
            "tags": tags,
        },
        files={"asset_data": (id, asset_data)},
        return_type=AssetInfo,
    )


def delete_asset(id: str, remove_dependents: bool = False) -> None:
    rest.call(rest.Method.DELETE, f"{URL}/assets/{id}", params={"remove_dependents": remove_dependents})


def asset_exists(id: str) -> bool:
    return rest.call(rest.Method.GET, f"{URL}/assets/{id}/exists", return_type=bool)
