python_library(
    dependencies = [
        ":VERSION"
    ]
)

arcor2_python_distribution(
    name="arcor2_calibration_data_dist",
    dependencies=[
        ":arcor2_calibration_data",
        ":py.typed"
    ],
    provides=arcor2_setup_py(
        name="arcor2_calibration_data",
        description="ARCOR2 - Augmented Reality Collaborative Robot."
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