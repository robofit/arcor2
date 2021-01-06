python_library(
    dependencies = [
        ":VERSION"
    ]
)

arcor2_python_distribution(
    name="arcor2_mocks_dist",
    dependencies=[
        ":arcor2_mocks",
        ":py.typed"
    ],
    provides=arcor2_setup_py(
        name="arcor2_mocks",
        description="ARCOR2 integration for Kinali services."
    ).with_binaries(
        {
            "arcor2_mock_project": "src/python/arcor2_mocks/scripts:mock_project",
            "arcor2_mock_scene": "src/python/arcor2_mocks/scripts:mock_scene"
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