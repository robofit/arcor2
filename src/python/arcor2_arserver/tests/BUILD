python_tests(
    runtime_package_dependencies=[
        "src/python/arcor2/scripts:upload_builtin_objects",
        "src/python/arcor2_mocks/scripts:mock_asset",
        "src/python/arcor2_mocks/scripts:mock_project",
        "src/python/arcor2_scene/scripts:scene",
        "src/python/arcor2_build/scripts:build",
        "src/python/arcor2_execution/scripts:execution",
        "src/python/arcor2_arserver/scripts:arserver",
    ],
)

python_test_utils(name="test_utils", sources=["conftest.py", "testutils.py"])
