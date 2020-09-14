python_library(
    dependencies = [
        ":VERSION"
    ]
)

python_distribution(
    name="arcor2_kinali_dist",
    dependencies=[
        ":arcor2_kinali",
        "src/python/arcor2_kinali/object_types",
        "src/python/arcor2_kinali/scripts",
        ":py.typed"
    ],
    provides=arcor2_setup_py(
        name="arcor2_kinali",
        description="ARCOR2 integration for Kinali services."
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