python_library(
    dependencies = [
        ":VERSION"
    ]
)

arcor2_python_distribution(
    name="arcor2_execution_rest_proxy_dist",
    dependencies=[
        ":arcor2_execution_rest_proxy",
        ":py.typed",
        "src/python/arcor2_execution_rest_proxy/scripts:execution_rest_proxy"  # TODO is it supposed to be here?
    ],
    provides=arcor2_setup_py(
        name="arcor2_execution_rest_proxy",
        description="REST Proxy for ARCOR2 Execution service."
    ).with_binaries(
        {
            "arcor2_execution_rest_proxy": "src/python/arcor2_execution_rest_proxy/scripts:execution_rest_proxy"
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