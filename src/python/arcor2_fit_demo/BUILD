python_library(
    dependencies = [
        ":VERSION"
    ]
)

arcor2_python_distribution(
    name="arcor2_fit_demo_dist",
    dependencies=[
        ":py.typed"
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