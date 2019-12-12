from setuptools import setup  # type: ignore
import arcor2

setup(
    name='arcor2',
    version=arcor2.version(),
    packages=['arcor2', 'arcor2.object_types', 'arcor2.source', 'arcor2.user_objects'],
    package_data={"arcor2": ["py.typed"]},
    entry_points={
                  'console_scripts': [
                      'arcor2_server = arcor2.nodes.server:main',
                      'arcor2_manager = arcor2.nodes.manager:main',
                      'arcor2_builder = arcor2.nodes.builder:main',
                      'arcor2_upload_ot = arcor2.scripts.upload_object_type:main',
                      'arcor2_swagger_models = arcor2.scripts.swagger_models:main'
                  ],
              },
    url='',
    license='',
    author='Robo@FIT',
    author_email='imaterna@fit.vutbr.cz',
    description='',
    install_requires=[
        'dataclasses',
        'horast',
        'typed_ast',
        'autopep8',
        'typed_astunparse',
        'static_typing',
        'websockets',
        'aiologger',
        'aiofiles',
        'dataclasses-jsonschema[fast-validation]',
        'apispec',
        'apispec_webframeworks',
        'flask',
        'requests',
        'numpy-quaternion',
        'fastcache',
        'bidict',
        'flask_swagger_ui'
    ],
    extras_require={
        'test': [
            'pytest',
            'websocket',
            'pytest-docker-compose',
            'openapi-spec-validator',
            'pyyaml'
            ],
        'docs': ['sphinx']
    },

    zip_safe=False
)
