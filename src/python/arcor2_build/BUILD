arcor2_python_distribution(
    name="arcor2_build",
    description="ARCOR2 Build",
    dependencies=[
        "src/python/arcor2_build/source",
        "src/python/arcor2_runtime",  # so the script can import e.g. ResourcesException
    ],
    binaries={"arcor2_build": "src/python/arcor2_build/scripts:build"},
)
