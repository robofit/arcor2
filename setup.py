from setuptools import setup

setup(
    name='arcor2',
    version='0.1',
    packages=['arcor2.tests', 'arcor2.user_objects'],
    url='',
    license='',
    author='Robo@FIT',
    author_email='',
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
        'dataclasses_json',
        'undecorated'
    ]
)
