python_binary(
    name = "execution",
    sources = ["execution.py"],
    dependencies = ["src/python/arcor2", "src/python/arcor2/object_types", "src/python/arcor2/parameter_plugins"],  # needed by the main script which run as subprocess of execution
    entry_point = "arcor2_execution.scripts.execution"
)

python_binary(
    name = "rest_proxy",
    sources = ["rest_proxy.py"],
    entry_point = "arcor2_execution.scripts.rest_proxy"
)