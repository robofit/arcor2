python_requirements(
    module_mapping={
        "numpy-quaternion": ["quaternion"],
        "PyYAML": ["yaml"],
        "Pillow": ["PIL"],
        "lru-dict": ["lru"],
        "opencv-contrib-python": ["cv2"],
        "websocket-client": ["websocket"],
        "pyhumps": ["humps"],
        "pyserial": ["serial"],
        "python-dateutil": ["dateutil"],
    },
    overrides={
        "apispec-webframeworks": {
            "dependencies": ["#setuptools", "#Flask"]
        },  # https://github.com/marshmallow-code/apispec-webframeworks/issues/99
        "fanucpy": {"dependencies": ["#sqlalchemy"]},  # https://github.com/torayeff/fanucpy/issues/7
    },
)
