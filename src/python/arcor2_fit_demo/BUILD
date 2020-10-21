python_library(
    dependencies = [
        ":VERSION"
    ]
)

arcor2_python_distribution(
    name="arcor2_fit_demo_dist",
    dependencies=[
        ":arcor2_fit_demo",
        ":py.typed",
        "src/python/arcor2_fit_demo/object_types",
        "src/python/arcor2_fit_demo/data:dobot-m1",
        "src/python/arcor2_fit_demo/data:dobot-magician",
        "src/python/arcor2_fit_demo/scripts:upload_objects"  # TODO why is this necessary?
    ],
    provides=arcor2_setup_py(
        name="arcor2_fit_demo",
        description="ARCOR2 - Augmented Reality Collaborative Robot."
    ).with_binaries(
        {
            "arcor2_fit_demo_upload_objects": "src/python/arcor2_fit_demo/scripts:upload_objects"
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