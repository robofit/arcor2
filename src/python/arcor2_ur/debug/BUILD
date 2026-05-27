python_sources(
    name="lib",
    dependencies=[
        "src/python/arcor2_ur/data:urdf_assets",
    ],
)

pex_binary(
    name="debug",
    entry_point="arcor2_ur.debug.debug",
    dependencies=[
        ":lib",
        "src/python/arcor2_ur/scripts:ur",
        "src/python/arcor2_ur/scripts:robot_publisher",
    ],
)

pex_binary(
    name="box_in_path_debug",
    entry_point="arcor2_ur.debug.box_in_path_debug",
    dependencies=[
        ":lib",
        "src/python/arcor2_ur/scripts:ur",
        "src/python/arcor2_ur/scripts:robot_publisher",
    ],
)