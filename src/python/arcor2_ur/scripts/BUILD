python_sources()

arcor2_pex_binary(
    name="ur",
    dependencies=["3rdparty#lark", "src/python/arcor2_ur/data:moveit.yaml"],
)
arcor2_pex_binary(
    name="upload_objects", dependencies=["src/python/arcor2_ur/data/urdf:ur5e"]
)

arcor2_pex_binary(
    name="robot_publisher",
    dependencies=["3rdparty#PyYAML", "3rdparty#numpy"],
)
