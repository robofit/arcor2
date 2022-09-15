python_tests(
    name="test_calibration.py",
    runtime_package_dependencies=["src/python/arcor2_calibration/scripts:calibration"],
    sources=["test_calibration.py"],
)

python_tests(
    name="test_estimate_camera_pose.py", sources=["test_estimate_camera_pose.py"], dependencies=[":markers.png"]
)

resources(name="markers.png", sources=["markers.png"])
