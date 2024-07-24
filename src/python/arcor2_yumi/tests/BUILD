python_tests(
    interpreter_constraints=["==3.11.*"],
    runtime_package_dependencies=[
        "src/python/arcor2_mocks/scripts:mock_asset",
        "src/python/arcor2_mocks/scripts:mock_project",
        "src/python/arcor2_scene/scripts:scene",
        "src/python/arcor2_build/scripts:build",
        "src/python/arcor2_execution/scripts:execution",
        "src/python/arcor2_arserver/scripts:arserver",
        "src/python/arcor2_yumi/scripts:upload_objects",
    ]
)

python_test_utils(name="test_utils", dependencies=["src/python/arcor2_arserver/tests:test_utils"])
