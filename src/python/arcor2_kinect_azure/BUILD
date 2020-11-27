python_library(
    dependencies = [
        ":VERSION"
    ]
)

arcor2_python_distribution(
    name="arcor2_kinect_azure_dist",
    dependencies=[
        ":arcor2_kinect_azure",
        ":py.typed"
    ],
    provides=arcor2_setup_py(
        name="arcor2_kinect_azure",
        description="REST API for Kinect Azure."
    ).with_binaries(
        {
            "arcor2_kinect_azure": "src/python/arcor2_kinect_azure/scripts:kinect_azure"
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