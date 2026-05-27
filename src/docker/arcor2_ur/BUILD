shell_source(name="start.sh", source="start.sh")

docker_image(
    name="arcor2_ur",
    repository="arcor2/arcor2_ur",
    dependencies=[
        ":start.sh",
        "build-support:install_ur_dependencies.sh",
        "src/python/arcor2_ur/scripts:ur",
        "src/python/arcor2_ur/scripts:robot_publisher",
    ],
    image_tags=["1.8.0"],
)
