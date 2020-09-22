from setuptools import setup, find_packages  # type: ignore

setup(
    name='arcor2',
    version_config={
            "template": "{tag}.dev{cc}",
            "starting_version": "0.1.0"
        },
    include_package_data=True,
    packages=find_packages(exclude=["*.tests", "*.tests.*", "tests.*", "tests"]),
    package_data={"arcor2": ["py.typed"]},
    entry_points={
                  'console_scripts': [
                      'arcor2_server = arcor2.nodes.server:main',
                      'arcor2_execution = arcor2.nodes.execution:main',
                      'arcor2_build = arcor2.nodes.build:main',
                      'arcor2_upload_ot = arcor2.scripts.upload_object_type:main',
                      'arcor2_upload_builtin_objects = arcor2.scripts.upload_builtin_objects:main',
                      'arcor2_swagger_models = arcor2.scripts.swagger_models:main',
                      'arcor2_execution_proxy = arcor2.nodes.execution_proxy:main',
                      'arcor2_broadcaster = arcor2.nodes.broadcaster:main',
                      'arcor2_project_mock = arcor2.nodes.project_mock:main',
                      'arcor2_scene_mock = arcor2.nodes.scene_mock:main'
                  ],
              },
    url='https://github.com/robofit/arcor2',
    license='LGPL',
    author='Robo@FIT',
    author_email='imaterna@fit.vut.cz',
    description='',
    setup_requires=['another-setuptools-git-version'],
    install_requires=[
        'dataclasses',
        'horast',
        'typed_ast',
        'autopep8',
        'typed_astunparse',
        'static_typing',
        'websockets',
        'aiologger',
        'dataclasses-jsonschema[fast-validation]',
        'apispec',
        'apispec_webframeworks',
        'flask',
        'requests',
        'cython',  # dependency of numpy, for some reason not installed automatically...
        'numpy-quaternion',
        'flask_swagger_ui',
        'websocket-client',
        'pyyaml',  # dependency of apispec, for some reason not installed automatically...
        'Pillow',
        'aiorun',
        'flask-cors',
        'typing_inspect',
        'semver',
        'lru-dict'
    ],
    extras_require={
        'test': [
            'pytest',
            'pytest-repeat',
            'pytest-randomly',
            'openapi-spec-validator',
            'flake8',
            'mypy',
            'flake8-import-order',
            'flake8-tidy-imports',
            'flake8-annotations-coverage',
            'flake8-pytest-style',
            'flake8-bugbear'
            ],
        'docs': ['sphinx']
    },
    zip_safe=False,
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Environment :: No Input/Output (Daemon)',
        'Intended Audience :: Developers',
        'Topic :: Software Development :: Build Tools',
        'License :: OSI Approved :: GNU Lesser General Public License v3 (LGPLv3)',
        'Programming Language :: Python :: 3.8',
        'Natural Language :: English',
        'Topic :: Scientific/Engineering'
    ]
)
