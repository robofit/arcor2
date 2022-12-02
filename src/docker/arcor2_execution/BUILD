shell_source(name="start.sh", source="start.sh")

docker_image(
    name="arcor2_execution", repository="arcor2/arcor2_execution", dependencies=[":start.sh"], image_tags=["0.22.0"]
)
