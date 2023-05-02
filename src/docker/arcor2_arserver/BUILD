shell_source(name="start.sh", source="start.sh")

docker_image(
    name="arcor2_arserver", repository="arcor2/arcor2_arserver", dependencies=[":start.sh"], image_tags=["1.0.2"]
)
