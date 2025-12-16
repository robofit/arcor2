# arcor2_storage

Combined ARCOR2 Project and Asset service. It stores scenes, object types, projects (including parameters and sources), models, and also raw asset files. Data are persisted locally in SQLite.

## Environment variables

- `ARCOR2_STORAGE_SERVICE_PORT` (default `10000`) - listen port.
- `ARCOR2_STORAGE_DB_PATH` (default `/data/arcor2_storage.sqlite`) - path to SQLite DB. Directory is created automatically.
- `ARCOR2_FLASK_DEBUG` - if set, enables verbose Flask error output.

## API

The service exposes the same REST API that was previously provided by the separate `project` and `asset` services (2.0.0), just merged under one host. Swagger is available at `/swagger/`.
