python_library(
    dependencies = [
        ":VERSION"
    ]
)

python_distribution(
    name="arcor2_build_dist",
    dependencies=[
        ":arcor2_build",
        ":py.typed",
        "src/python/arcor2_build/scripts:build",
        "src/python/arcor2_build/source"
    ],
    provides=arcor2_setup_py(
        name="arcor2_build",
        version="0.8.0",
        description="ARCOR2 - Augmented Reality Collaborative Robot."
    ).with_binaries(
        {
            "arcor2_build": "src/python/arcor2_build/scripts:build"
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