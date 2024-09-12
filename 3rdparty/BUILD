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
    },
)

python_requirements(
    name="mypy",
    source="mypy-requirements.txt",
    resolve="mypy",
)

python_requirements(
    name="pytest",
    source="pytest-requirements.txt",
    resolve="pytest",
)

python_requirements(
    name="flake8",
    source="flake8-requirements.txt",
    resolve="flake8",
)

python_requirements(
    name="setuptools",
    source="setuptools-requirements.txt",
    resolve="setuptools",
)