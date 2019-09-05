from setuptools import setup  # type: ignore

setup(
    name='arcor2',
    version='0.1',
    packages=['arcor2', 'arcor2.object_types', 'arcor2.source', 'arcor2.user_objects'],
    package_data={"arcor2": ["py.typed"]},
    entry_points={
                  'console_scripts': [
                      'arcor2_server = arcor2.nodes.server:main',
                      'arcor2_manager = arcor2.nodes.manager:main',
                      'arcor2_persistent_storage = arcor2.nodes.persistent_storage:main',
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
        'pymongo',
        'dataclasses',
        'horast',
        'typed_ast',
        'autopep8',
        'typed_astunparse',
        'static_typing',
        'websockets',
        'aiologger',
        'motor',
        'aiofiles',
        'undecorated',
        'dataclasses-jsonschema[fast-validation]',
        'pytest',
        'apispec',
        'apispec_webframeworks',
        'flask',
        'requests'
    ],
    tests_require=[
        'websocket'
    ],
    zip_safe=False
)
