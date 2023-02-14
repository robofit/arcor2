shell_source(name="start.sh", source="start.sh")

docker_image(
    name="arcor2_calibration", repository="arcor2/arcor2_calibration", dependencies=[":start.sh"], image_tags=["1.0.0"]
)