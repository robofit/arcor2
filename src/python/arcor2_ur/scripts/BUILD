python_sources(interpreter_constraints=["==3.12.*"])

arcor2_pex_binary(name="ur", interpreter_constraints=["==3.12.*"],dependencies=["3rdparty#lark", "src/python/arcor2_ur/data:moveit.yaml"])
arcor2_pex_binary(name="upload_objects", dependencies=["src/python/arcor2_ur/data/urdf:ur5e"], interpreter_constraints=["==3.12.*"])