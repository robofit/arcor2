python_library(
    dependencies = [
        ":VERSION"
    ]
)

arcor2_python_distribution(
    name="arcor2_dobot_dist",
    dependencies=[
        ":arcor2_dobot",
        ":py.typed"
    ],
    provides=arcor2_setup_py(
        name="arcor2_dobot",
        description="ARCOR2 - Dobot Web API."
    ).with_binaries(
        {
            "arcor2_dobot": "src/python/arcor2_dobot/scripts:dobot"
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