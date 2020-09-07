python_library(
    dependencies = [
        ":VERSION"
    ]
)

python_distribution(
    name="arcor2_arserver_data_dist",
    dependencies=[
        ":arcor2_arserver_data",
        ":py.typed",
        "src/python/arcor2_arserver_data/events",
        "src/python/arcor2_arserver_data/rpc"
    ],
    provides=arcor2_setup_py(
        name="arcor2_arserver_data",
        description="ARCOR2 - Augmented Reality Collaborative Robot."
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