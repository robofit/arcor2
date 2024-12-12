shell_source(name="start.sh", source="start.sh")
docker_image(name="arcor2_ur", repository="arcor2/arcor2_ur", dependencies=[":start.sh", "build-support:install_ur_dependencies.sh"], image_tags=["1.5.0"])
