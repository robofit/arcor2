shell_source(name="start.sh", source="start.sh")

docker_image(
    name="arcor2_kinect_azure",
    repository="arcor2/arcor2_kinect_azure",
    dependencies=[":start.sh", "build-support:install_kinect_prerequisites.sh"],
    image_tags=["0.5.0"],
)
