python_sources()

arcor2_pex_binary(
    name="execution",
    dependencies=[
        "src/python/arcor2",
        "src/python/arcor2_object_types",
        "src/python/arcor2_runtime",
        "3rdparty#websocket-client",
    ],  # needed by the main script which run as subprocess of execution
)
