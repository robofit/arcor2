python_library(
    dependencies = [
        ":VERSION"
    ]
)

arcor2_python_distribution(
    name="arcor2_kinali_dist",
    dependencies=[
        ":py.typed",
    ],
    provides=arcor2_setup_py(
        name="arcor2_kinali",
        description="ARCOR2 integration for Kinali services."
    ).with_binaries(
        {
            "arcor2_kinali_upload_objects": "src/python/arcor2_kinali/scripts:upload_objects"
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