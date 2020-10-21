python_library(
    dependencies = [
        ":VERSION"
    ]
)

arcor2_python_distribution(
    name="arcor2_calibration_dist",
    dependencies=[
        ":arcor2_calibration",
        ":py.typed",
        "src/python/arcor2_calibration/scripts:calibration"  # TODO why is this necessary?
    ],
    provides=arcor2_setup_py(
        name="arcor2_calibration",
        description="ARCOR2 - Augmented Reality Collaborative Robot."
    ).with_binaries(
        {
            "arcor2_calibration": "src/python/arcor2_calibration/scripts:calibration"
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