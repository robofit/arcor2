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
        ":py.typed",
        "src/python/arcor2_kinali/scripts:upload_objects"  # TODO why is this necessary?
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