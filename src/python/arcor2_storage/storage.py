from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable, Type, TypeVar, cast

from dataclasses_jsonschema import JsonSchemaMixin

from arcor2.data.common import Project, ProjectParameter, ProjectSources, Scene, SceneObjectOverride
from arcor2.data.object_type import MODEL_MAPPING, Mesh, Model3dType, Models, ObjectType
from arcor2_storage.client import Asset

DataClass = TypeVar("DataClass", bound=JsonSchemaMixin)


@dataclass
class StoredAsset:
    info: Asset
    data: bytes


def _dump(dc: JsonSchemaMixin) -> str:
    return dc.to_json()


def _load(data: str, cls: Type[DataClass]) -> DataClass:
    return cls.from_json(data)


class Database:
    def __init__(self, path: str):
        self.path = path
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    # ------------------------------------------------------------------ assets

    def list_asset_info(self) -> list[Asset]:
        with self._connect() as conn:
            rows = conn.execute("SELECT info_json FROM assets").fetchall()
        return [_load(row["info_json"], Asset) for row in rows]

    def save_asset(self, asset: Asset, data: bytes, *, replace: bool = True) -> None:
        with self._connect() as conn:
            if not replace and self.asset_exists(asset.id, conn):
                raise ValueError(f"Asset {asset.id} already exists.")

            conn.execute(
                "INSERT INTO assets (id, info_json, data) VALUES (?, ?, ?) "
                "ON CONFLICT(id) DO UPDATE SET info_json=excluded.info_json, data=excluded.data",
                (asset.id, _dump(asset), data),
            )

    def asset_exists(self, asset_id: str, conn: sqlite3.Connection | None = None) -> bool:
        own_conn = conn is None
        connection = conn or self._connect()
        try:
            return connection.execute("SELECT 1 FROM assets WHERE id=?", (asset_id,)).fetchone() is not None
        finally:
            if own_conn:
                connection.close()

    def get_asset(self, asset_id: str) -> StoredAsset | None:
        with self._connect() as conn:
            row = conn.execute("SELECT info_json, data FROM assets WHERE id=?", (asset_id,)).fetchone()

        if row is None:
            return None

        return StoredAsset(_load(row["info_json"], Asset), cast(bytes, row["data"]))

    def delete_asset(self, asset_id: str) -> bool:
        with self._connect() as conn:
            cur = conn.execute("DELETE FROM assets WHERE id=?", (asset_id,))
            return cur.rowcount > 0

    # ------------------------------------------------------------------ scenes

    def save_scene(self, scene: Scene) -> None:
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO scenes (id, scene_json) VALUES (?, ?) "
                "ON CONFLICT(id) DO UPDATE SET scene_json=excluded.scene_json",
                (scene.id, _dump(scene)),
            )

    def get_scene(self, scene_id: str) -> Scene | None:
        with self._connect() as conn:
            row = conn.execute("SELECT scene_json FROM scenes WHERE id=?", (scene_id,)).fetchone()
        return None if row is None else _load(row["scene_json"], Scene)

    def list_scenes(self) -> Iterable[Scene]:
        with self._connect() as conn:
            rows = conn.execute("SELECT scene_json FROM scenes").fetchall()
        return (_load(row["scene_json"], Scene) for row in rows)

    def delete_scene(self, scene_id: str) -> bool:
        with self._connect() as conn:
            cur = conn.execute("DELETE FROM scenes WHERE id=?", (scene_id,))
        return cur.rowcount > 0

    # -------------------------------------------------------------- object types

    def save_object_type(self, obj_type: ObjectType) -> None:
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO object_types (id, object_type_json) VALUES (?, ?) "
                "ON CONFLICT(id) DO UPDATE SET object_type_json=excluded.object_type_json",
                (obj_type.id, _dump(obj_type)),
            )

    def get_object_type(self, obj_type_id: str) -> ObjectType | None:
        with self._connect() as conn:
            row = conn.execute("SELECT object_type_json FROM object_types WHERE id=?", (obj_type_id,)).fetchone()
        return None if row is None else _load(row["object_type_json"], ObjectType)

    def delete_object_type(self, obj_type_id: str) -> bool:
        with self._connect() as conn:
            cur = conn.execute("DELETE FROM object_types WHERE id=?", (obj_type_id,))
        return cur.rowcount > 0

    def object_type_ids(self) -> set[str]:
        with self._connect() as conn:
            rows = conn.execute("SELECT id FROM object_types").fetchall()
        return {row["id"] for row in rows}

    def list_object_types(self) -> Iterable[ObjectType]:
        with self._connect() as conn:
            rows = conn.execute("SELECT object_type_json FROM object_types").fetchall()
        return (_load(row["object_type_json"], ObjectType) for row in rows)

    # ------------------------------------------------------------------ models

    def save_model(self, model: Models) -> None:
        model_type = model.type()
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO models (id, type, model_json) VALUES (?, ?, ?) "
                "ON CONFLICT(id) DO UPDATE SET type=excluded.type, model_json=excluded.model_json",
                (model.id, model_type.value, _dump(model)),
            )

    def get_model(self, model_id: str) -> Models | None:
        with self._connect() as conn:
            row = conn.execute("SELECT type, model_json FROM models WHERE id=?", (model_id,)).fetchone()

        if row is None:
            return None

        model_type = Model3dType(row["type"])
        cls = MODEL_MAPPING[model_type]
        return _load(row["model_json"], cls)

    def delete_model(self, model_id: str) -> bool:
        with self._connect() as conn:
            cur = conn.execute("DELETE FROM models WHERE id=?", (model_id,))
        return cur.rowcount > 0

    def list_models(self) -> list[Models]:
        with self._connect() as conn:
            rows = conn.execute("SELECT type, model_json FROM models").fetchall()

        models: list[Models] = []
        for row in rows:
            model_type = Model3dType(row["type"])
            cls = MODEL_MAPPING[model_type]
            models.append(_load(row["model_json"], cls))

        return models

    def list_meshes(self) -> list[Mesh]:
        with self._connect() as conn:
            rows = conn.execute("SELECT model_json FROM models WHERE type=?", (Model3dType.MESH.value,)).fetchall()
        return [_load(row["model_json"], Mesh) for row in rows]

    # ------------------------------------------------------------------ projects

    def save_project(self, project: Project) -> None:
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO projects (id, project_json) VALUES (?, ?) "
                "ON CONFLICT(id) DO UPDATE SET project_json=excluded.project_json",
                (project.id, _dump(project)),
            )

    def get_project(self, project_id: str) -> Project | None:
        with self._connect() as conn:
            row = conn.execute("SELECT project_json FROM projects WHERE id=?", (project_id,)).fetchone()
        return None if row is None else _load(row["project_json"], Project)

    def list_projects(self) -> Iterable[Project]:
        with self._connect() as conn:
            rows = conn.execute("SELECT project_json FROM projects").fetchall()
        return (_load(row["project_json"], Project) for row in rows)

    def delete_project(self, project_id: str) -> bool:
        with self._connect() as conn:
            cur = conn.execute("DELETE FROM projects WHERE id=?", (project_id,))
            conn.execute("DELETE FROM project_sources WHERE project_id=?", (project_id,))
            conn.execute("DELETE FROM project_parameters WHERE project_id=?", (project_id,))
            conn.execute("DELETE FROM object_parameters WHERE project_id=?", (project_id,))
        return cur.rowcount > 0

    # --------------------------------------------------------------- parameters

    def get_project_parameters(self, project_id: str) -> list[ProjectParameter]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT params_json FROM project_parameters WHERE project_id=?", (project_id,)
            ).fetchone()
        if row is None:
            return []
        return [ProjectParameter.from_dict(item) for item in json.loads(row["params_json"])]

    def set_project_parameters(self, project_id: str, parameters: list[ProjectParameter], modified: datetime) -> None:
        payload = [param.to_dict() for param in parameters]
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO project_parameters (project_id, params_json, modified) VALUES (?, ?, ?) "
                "ON CONFLICT(project_id) DO UPDATE SET params_json=excluded.params_json, modified=excluded.modified",
                (project_id, json.dumps(payload), modified.isoformat()),
            )

    def get_object_parameters(self, project_id: str) -> list[SceneObjectOverride]:
        with self._connect() as conn:
            row = conn.execute("SELECT params_json FROM object_parameters WHERE project_id=?", (project_id,)).fetchone()
        if row is None:
            return []
        return [SceneObjectOverride.from_dict(item) for item in json.loads(row["params_json"])]

    def set_object_parameters(self, project_id: str, parameters: list[SceneObjectOverride], modified: datetime) -> None:
        payload = [param.to_dict() for param in parameters]
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO object_parameters (project_id, params_json, modified) VALUES (?, ?, ?) "
                "ON CONFLICT(project_id) DO UPDATE SET params_json=excluded.params_json, modified=excluded.modified",
                (project_id, json.dumps(payload), modified.isoformat()),
            )

    # ------------------------------------------------------------- project code

    def save_project_sources(self, sources: ProjectSources) -> None:
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO project_sources (project_id, sources_json) VALUES (?, ?) "
                "ON CONFLICT(project_id) DO UPDATE SET sources_json=excluded.sources_json",
                (sources.id, _dump(sources)),
            )

    def get_project_sources(self, project_id: str) -> ProjectSources | None:
        with self._connect() as conn:
            row = conn.execute("SELECT sources_json FROM project_sources WHERE project_id=?", (project_id,)).fetchone()
        return None if row is None else _load(row["sources_json"], ProjectSources)

    # ------------------------------------------------------------------ helpers

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS assets (
                    id TEXT PRIMARY KEY,
                    info_json TEXT NOT NULL,
                    data BLOB NOT NULL
                );
                CREATE TABLE IF NOT EXISTS scenes (
                    id TEXT PRIMARY KEY,
                    scene_json TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS object_types (
                    id TEXT PRIMARY KEY,
                    object_type_json TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS models (
                    id TEXT PRIMARY KEY,
                    type TEXT NOT NULL,
                    model_json TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS projects (
                    id TEXT PRIMARY KEY,
                    project_json TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS project_sources (
                    project_id TEXT PRIMARY KEY,
                    sources_json TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS project_parameters (
                    project_id TEXT PRIMARY KEY,
                    params_json TEXT NOT NULL,
                    modified TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS object_parameters (
                    project_id TEXT PRIMARY KEY,
                    params_json TEXT NOT NULL,
                    modified TEXT NOT NULL
                );
                """
            )
