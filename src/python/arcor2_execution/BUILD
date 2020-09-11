python_library(
    dependencies = [
        ":VERSION"
    ]
)

python_distribution(
    name="arcor2_execution_dist",
    dependencies=[
        ":arcor2_execution",
        ":py.typed"
    ],
    provides=arcor2_setup_py(
        name="arcor2_execution",
        description="ARCOR2 - Augmented Reality Collaborative Robot."
    ).with_binaries(
        {
            "arcor2_execution": "src/python/arcor2_execution/scripts:execution"
            }
        )
)

resources(
    name = "py.typed",
    sources = ["py.typed"],
)

resources(
    name = "VERSION",
    sources = ["VERSION"]
)