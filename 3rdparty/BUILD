python_requirements(
    module_mapping={
            "numpy-quaternion": ["quaternion"],
            "PyYAML": ["yaml"],
            "Pillow": ["PIL"],
            "lru-dict": ["lru"],
            "opencv-contrib-python": ["cv2"],
            "websocket-client": ["websocket"],
            "pyhumps": ["humps"],
            "dataclasses-jsonschema-rereleased": ["dataclasses_jsonschema"],
            "horast-rereleased": ["horast"],
            "pyserial": ["serial"]
          },
    overrides={
        "openapi-spec-validator": {"dependencies": [":setuptools"]},  # https://github.com/p1c2u/openapi-spec-validator/issues/133
        "apispec-webframeworks": {"dependencies": [":setuptools", ":Flask"]},  # https://github.com/marshmallow-code/apispec-webframeworks/issues/99
    },
)