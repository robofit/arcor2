python_library(
    dependencies = [
        ":VERSION"
    ]
)

arcor2_python_distribution(
    name="arcor2_dist",
    dependencies=[
        ":arcor2",
        ":py.typed",
        "src/python/arcor2/clients",
        "src/python/arcor2/data",
        "src/python/arcor2/object_types",
        "src/python/arcor2/parameter_plugins",
        "src/python/arcor2/source",
        "src/python/arcor2/test_objects",
        "src/python/arcor2/scripts:upload_builtin_objects"  # TODO why is this necessary?
    ],
    provides=arcor2_setup_py(
        name="arcor2",
        description="ARCOR2 - Augmented Reality Collaborative Robot."
    ).with_binaries(
        {
            "arcor2_upload_builtin_objects": "src/python/arcor2/scripts:upload_builtin_objects"
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