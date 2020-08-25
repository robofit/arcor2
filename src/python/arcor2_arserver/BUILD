python_library(
    dependencies = [
        ":VERSION",
        "src/python/arcor2_execution_data/events.py",  # TODO why is this needed?
        "src/python/arcor2_execution_data/rpc.py",  # TODO why is this needed?
        "src/python/arcor2_calibration_data/client.py"  # TODO why is this needed?
    ]
)

python_distribution(
    name="arcor2_arserver_dist",
    dependencies=[
        ":arcor2_arserver",
        ":py.typed",
        "src/python/arcor2_arserver/clients",
        "src/python/arcor2_arserver/object_types",
        "src/python/arcor2_arserver/rpc"
    ],
    provides=arcor2_setup_py(
        name="arcor2_arserver",
        version="0.8.0",
        description="ARCOR2 - Augmented Reality Collaborative Robot."
    ).with_binaries(
        {
            "arcor2_arserver": "src/python/arcor2_arserver/scripts:arserver",
            "arcor2_broadcaster": "src/python/arcor2_arserver/scripts:broadcaster"
            }
        )
)

resources(
    name = "py.typed",
    sources = ["py.typed"],
)

resources(
    name = "VERSION",
    sources = ["VERSION"],
)