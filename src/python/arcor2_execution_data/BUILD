python_library(
    dependencies = [
        ":VERSION"
    ]
)

python_distribution(
    name="arcor2_execution_data_dist",
    dependencies=[
        ":arcor2_execution_data",
        ":py.typed"
    ],
    provides=arcor2_setup_py(
        name="arcor2_execution_data",
        version="0.8.0",
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