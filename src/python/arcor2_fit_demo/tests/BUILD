python_tests(
    dependencies=[
        "src/python/arcor2_arserver/tests:test_utils",
    ],
    runtime_package_dependencies=[
        "src/python/arcor2_storage/scripts:storage",
        "src/python/arcor2_scene/scripts:scene",
        "src/python/arcor2_build/scripts:build",
        "src/python/arcor2_runtime",
        "src/python/arcor2_execution_data",
        "src/python/arcor2_execution/scripts:execution",
        "src/python/arcor2_arserver/scripts:arserver",
        "src/python/arcor2_fit_demo/scripts:upload_objects",
    ],
)

python_test_utils(name="test_utils", dependencies=["src/python/arcor2_arserver/tests:test_utils"])
