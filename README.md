# ARCOR2

**ARCOR** stands for **A**ugmented **R**eality **C**ollaborative **R**obot. It is a system for simplified programming of collaborative robots based on augmented reality developed by [Robo@FIT](https://www.fit.vut.cz/research/group/robo/.en). 

This repository contains the backend solution. It can be easily tested out or deployed using [docker images](https://hub.docker.com/u/arcor2). Unity-based client application for ARCore-supported tablets is available [here](https://github.com/robofit/arcor2_editor).

Development is supported by [Test-it-off: Robotic offline product testing](https://www.fit.vut.cz/research/project/1308/) project (Ministry of Industry and Trade of the Czech Republic).

Quick Links:
 - [Terminology](#terminology)
 - [Services](#services)
 - [Development](#development)
 - [Contributing](#contributing)
 - [Releases](#releases)
 - [Publications](#publications)

## Terminology

 - Scene
   - The layout of the workspace.
   - Consists of action objects' instances and their parameters.
 - Project
   - User-defined program based on a scene.
   - Contains action points, actions, and their parameters, program flow definition (logic).
 - Action Point
   - Acts as a spatial anchor.
   - Defined within a project.
   - Has a 3D position, may contain ```0-n``` orientations and/or robot joints. 
 - Action Object
   - A class derived from [Generic](src/python/arcor2/object_types/abstract.py).
   - Its methods (with special annotation) become Actions.
   - Support for new service/device/robot is added through writing a class definition.
   - It may or may not have pose, collision model, URDF model (robots only).
 - Action Object Instance
   - An action object with given parameters, pose, etc. within a scene, project, or main script.
 - Action
   - Action object method that can be parametrized and called from a project.
 - Action Instance
   - Concrete action with a unique ID and name added to a specific action point in the project.
 - Execution Package
   - Self-contained package generated from scene, project, and involved action objects.
 - Main Script
   - Part of the execution package.
   - An executable script that creates instances of the objects and contains the logic of the project.
   - Can be optionally hand-written.
   - Logic can be manually updated and then the script could be converted back to the project (upcoming feature).

## Services

 - [ARServer](src/python/arcor2_arserver/README.md)
   - The central point for user interfaces (e.g. instances of the AREditor).
   - Provides API (RPC, events) for its clients, mediates communication with other services.
 - [Build](src/python/arcor2_build/README.md)
   - Transforms projects created in the AR environment into execution packages.
 - [Execution](src/python/arcor2_execution/README.md)
   - Runs execution packages generated by the Build service.
   - Provides data about packages and execution state (what step of the program with what parameters is currently running) to the ARServer / AREditor, controls the execution of the main script (pause, resume, stop).

Other services as Project and Scene (this repo provides [mocks](src/python/arcor2_mocks) for them) are being developed by [Kinali](https://www.kinali.cz/en/) and will be eventually published [here](https://gitlab.com/kinalisoft/test-it-off).
 
## Development

We use [Pants](https://www.pantsbuild.org/docs) to build the sources into Python distribution packages, run tests, etc. Packages do not contain ```setup.py``` file - this is generated during the build process.

## Contributing


 - When making PR, please make sure to rebase your commits first or at least merge last changes from `master` branch.
 - Ideally, PR should contain only one, clearly focused commit. If you have more commits, please squash them.
 - We use [Conventional Commits](https://www.conventionalcommits.org/en/v1.0.0/).
 - We use type annotations and [mypy](https://mypy.readthedocs.io/en/stable/). All code should have type annotations.
 - If possible, please also add tests with any new code.
 - If necessary, please do not forget do update also documentation.
 - Before commit:
   - run `./pants fmt ::` to get correct formatting.
   - run `./pants lint ::` to run flake8.
   - run `./pants tests ::` to run tests.
   - ...all of those are ran on CI but are much faster on localhost.

Any contribution is welcome!

### Testing

How to run all tests:
```bash
$ ./pants test ::
```

How to run a specific test:
```bash
$ ./pants test src/python/arcor2/data/tests
```


## Releases

### arcor2

[README](src/python/arcor2/README.md) | [CHANGELOG](src/python/arcor2/CHANGELOG.md)
 
 - 2021-03-03: [0.12.0](https://github.com/robofit/arcor2/releases/tag/arcor2%2F0.12.0) ([pypi](https://pypi.org/project/arcor2/0.12.0/)).

 - 2021-02-09: [0.11.1](https://github.com/robofit/arcor2/releases/tag/arcor2%2F0.11.1) ([pypi](https://pypi.org/project/arcor2/0.11.1/)).

 - 2021-02-08: [0.11.0](https://github.com/robofit/arcor2/releases/tag/arcor2%2F0.11.0) ([pypi](https://pypi.org/project/arcor2/0.11.0/)).

 
### arcor2_arserver

[README](src/python/arcor2_arserver/README.md) | [CHANGELOG](src/python/arcor2_arserver/CHANGELOG.md)

 - 2021-03-03: [0.13.0](https://github.com/robofit/arcor2/releases/tag/arcor2_arserver%2F0.13.0) ([docker](https://hub.docker.com/r/arcor2/arcor2_arserver/tags?page=1&ordering=last_updated&name=0.13.0), [pypi](https://pypi.org/project/arcor2-arserver/0.13.0/)).

 - 2021-02-08: [0.12.0](https://github.com/robofit/arcor2/releases/tag/arcor2_arserver%2F0.12.0) ([docker](https://hub.docker.com/r/arcor2/arcor2_arserver/tags?page=1&ordering=last_updated&name=0.12.0), [pypi](https://pypi.org/project/arcor2-arserver/0.12.0/)).

 - 2020-12-14: [0.11.0](https://github.com/robofit/arcor2/releases/tag/arcor2_arserver%2F0.11.0) ([docker](https://hub.docker.com/r/arcor2/arcor2_arserver/tags?page=1&ordering=last_updated&name=0.11.0), [pypi](https://pypi.org/project/arcor2-arserver/0.11.0/)).

 
### arcor2_arserver_data

[README](src/python/arcor2_arserver_data/README.md) | [CHANGELOG](src/python/arcor2_arserver_data/CHANGELOG.md)

 - 2021-03-03: [0.12.0](https://github.com/robofit/arcor2/releases/tag/arcor2_arserver_data%2F0.12.0) ([pypi](https://pypi.org/project/arcor2-arserver-data/0.12.0/)).

 - 2021-02-08: [0.11.0](https://github.com/robofit/arcor2/releases/tag/arcor2_arserver_data%2F0.11.0) ([pypi](https://pypi.org/project/arcor2-arserver-data/0.11.0/)).

 - 2020-12-14: [0.10.0](https://github.com/robofit/arcor2/releases/tag/arcor2_arserver_data%2F0.10.0) ([pypi](https://pypi.org/project/arcor2-arserver-data/0.10.0/)).


### arcor2_build

[README](src/python/arcor2_build/README.md) | [CHANGELOG](src/python/arcor2_build/CHANGELOG.md)

- 2021-03-03: [0.12.0](https://github.com/robofit/arcor2/releases/tag/arcor2_build%2F0.12.0) ([docker](https://hub.docker.com/r/arcor2/arcor2_build/tags?page=1&ordering=last_updated&name=0.12.0), [pypi](https://pypi.org/project/arcor2-build/0.12.0/)).

- 2021-02-08: [0.11.0](https://github.com/robofit/arcor2/releases/tag/arcor2_build%2F0.11.0) ([docker](https://hub.docker.com/r/arcor2/arcor2_build/tags?page=1&ordering=last_updated&name=0.11.0), [pypi](https://pypi.org/project/arcor2-build/0.11.0/)).

- 2020-12-14: [0.10.0](https://github.com/robofit/arcor2/releases/tag/arcor2_build%2F0.10.0) ([docker](https://hub.docker.com/r/arcor2/arcor2_build/tags?page=1&ordering=last_updated&name=0.10.0), [pypi](https://pypi.org/project/arcor2-build/0.10.0/)).

### arcor2_build_data

[README](src/python/arcor2_build_data/README.md) | [CHANGELOG](src/python/arcor2_build_data/CHANGELOG.md)

 - 2020-10-19: [0.8.1](https://github.com/robofit/arcor2/releases/tag/arcor2_build_data%2F0.8.1) ([pypi](https://pypi.org/project/arcor2-build-data/0.8.1/)).

 - 2020-09-24: [0.8.0](https://github.com/robofit/arcor2/releases/tag/arcor2_build_data%2F0.8.0) ([pypi](https://pypi.org/project/arcor2-build-data/0.8.0/)).

### arcor2_calibration

[README](src/python/arcor2_calibration/README.md) | [CHANGELOG](src/python/arcor2_calibration/CHANGELOG.md)

 - 2021-02-08: [0.2.0](https://github.com/robofit/arcor2/releases/tag/arcor2_calibration%2F0.2.0) ([docker](https://hub.docker.com/r/arcor2/arcor2_calibration/tags?page=1&ordering=last_updated&name=0.2.0), ([pypi](https://pypi.org/project/arcor2-calibration/0.2.0/)).

 - 2020-12-14: [0.1.1](https://github.com/robofit/arcor2/releases/tag/arcor2_calibration%2F0.1.1) ([pypi](https://pypi.org/project/arcor2-calibration/0.1.1/)).

### arcor2_calibration_data

[README](src/python/arcor2_calibration_data/README.md) | [CHANGELOG](src/python/arcor2_calibration_data/CHANGELOG.md)

 - 2021-02-08: [0.2.0](https://github.com/robofit/arcor2/releases/tag/arcor2_calibration_data%2F0.2.0) ([pypi](https://pypi.org/project/arcor2-calibration-data/0.2.0/)).

 - 2020-12-14: [0.1.1](https://github.com/robofit/arcor2/releases/tag/arcor2_calibration_data%2F0.1.1) ([pypi](https://pypi.org/project/arcor2-calibration-data/0.1.1/)).

### arcor2_execution

[README](src/python/arcor2_execution/README.md) | [CHANGELOG](src/python/arcor2_execution/CHANGELOG.md)

 - 2021-02-08: [0.11.0](https://github.com/robofit/arcor2/releases/tag/arcor2_execution%2F0.11.0) ([docker](https://hub.docker.com/r/arcor2/arcor2_execution/tags?page=1&ordering=last_updated&name=0.11.0), [pypi](https://pypi.org/project/arcor2-execution/0.11.0/)).

 - 2020-12-14: [0.10.0](https://github.com/robofit/arcor2/releases/tag/arcor2_execution%2F0.10.0) ([docker](https://hub.docker.com/r/arcor2/arcor2_execution/tags?page=1&ordering=last_updated&name=0.10.0), [pypi](https://pypi.org/project/arcor2-execution/0.10.0/)).

 - 2020-10-22: [0.9.0](https://github.com/robofit/arcor2/releases/tag/arcor2_execution%2F0.9.0) ([docker](https://hub.docker.com/r/arcor2/arcor2_execution/tags?page=1&ordering=last_updated&name=0.19.0), [pypi](https://pypi.org/project/arcor2-execution/0.9.0/)).
 
### arcor2_execution_data

[README](src/python/arcor2_execution_data/README.md) | [CHANGELOG](src/python/arcor2_execution_data/CHANGELOG.md)

 - 2021-02-08: [0.10.0](https://github.com/robofit/arcor2/releases/tag/arcor2_execution_data%2F0.10.0) ([pypi](https://pypi.org/project/arcor2-execution-data/0.10.0/)).

 - 2020-10-22: [0.9.0](https://github.com/robofit/arcor2/releases/tag/arcor2_execution_data%2F0.9.0) ([pypi](https://pypi.org/project/arcor2-execution-data/0.9.0/)).

 - 2020-10-19: [0.8.1](https://github.com/robofit/arcor2/releases/tag/arcor2_execution_data%2F0.8.1) ([pypi](https://pypi.org/project/arcor2-execution-data/0.8.1/)).
 
### arcor2_execution_rest_proxy

[README](src/python/arcor2_execution_rest_proxy/README.md) | [CHANGELOG](src/python/arcor2_execution_rest_proxy/CHANGELOG.md)

 - 2021-02-08: [0.9.0](https://github.com/robofit/arcor2/releases/tag/arcor2_execution_rest_proxy%2F0.9.0) ([docker](https://hub.docker.com/r/arcor2/arcor2_execution_proxy/tags?page=1&ordering=last_updated&name=0.9.0), [pypi](https://pypi.org/project/arcor2-execution-rest-proxy/0.9.0/)).

 - 2020-12-14: [0.8.3](https://github.com/robofit/arcor2/releases/tag/arcor2_execution_rest_proxy%2F0.8.3) ([docker](https://hub.docker.com/r/arcor2/arcor2_execution_proxy/tags?page=1&ordering=last_updated&name=0.8.3), [pypi](https://pypi.org/project/arcor2-execution-rest-proxy/0.8.3/)).

 - 2020-10-22: [0.8.2](https://github.com/robofit/arcor2/releases/tag/arcor2_execution_rest_proxy%2F0.8.2) ([docker](https://hub.docker.com/r/arcor2/arcor2_execution_proxy/tags?page=1&ordering=last_updated&name=0.8.2), [pypi](https://pypi.org/project/arcor2-execution-rest-proxy/0.8.2/)).
 
### arcor2_fit_demo

[README](src/python/arcor2_fit_demo/README.md) | [CHANGELOG](src/python/arcor2_fit_demo/CHANGELOG.md)

- 2021-03-03: [0.5.0](https://github.com/robofit/arcor2/releases/tag/arcor2_fit_demo%2F0.5.0) ([docker](https://hub.docker.com/r/arcor2/arcor2_upload_fit_demo/tags?page=1&ordering=last_updated&name=0.5.0), [pypi](https://pypi.org/project/arcor2-fit-demo/0.5.0/)).

- 2021-02-08: [0.4.0](https://github.com/robofit/arcor2/releases/tag/arcor2_fit_demo%2F0.4.0) ([docker](https://hub.docker.com/r/arcor2/arcor2_upload_fit_demo/tags?page=1&ordering=last_updated&name=0.4.0), [pypi](https://pypi.org/project/arcor2-fit-demo/0.4.0/)).

- 2020-12-14: [0.3.0](https://github.com/robofit/arcor2/releases/tag/arcor2_fit_demo%2F0.3.0) ([docker](https://hub.docker.com/r/arcor2/arcor2_upload_fit_demo/tags?page=1&ordering=last_updated&name=0.3.0), [pypi](https://pypi.org/project/arcor2-fit-demo/0.3.0/)).

### arcor2_kinali

[README](src/python/arcor2_kinali/README.md) | [CHANGELOG](src/python/arcor2_kinali/CHANGELOG.md)

- 2021-03-03: [0.12.0](https://github.com/robofit/arcor2/releases/tag/arcor2_kinali%2F0.12.0) ([docker](https://hub.docker.com/r/arcor2/arcor2_upload_kinali/tags?page=1&ordering=last_updated&name=0.12.0), [pypi](https://pypi.org/project/arcor2-kinali/0.12.0/)).

- 2021-02-09: [0.11.1](https://github.com/robofit/arcor2/releases/tag/arcor2_kinali%2F0.11.1) ([docker](https://hub.docker.com/r/arcor2/arcor2_upload_kinali/tags?page=1&ordering=last_updated&name=0.11.1), [pypi](https://pypi.org/project/arcor2-kinali/0.11.1/)).

- 2021-02-08: [0.11.0](https://github.com/robofit/arcor2/releases/tag/arcor2_kinali%2F0.11.0) ([docker](https://hub.docker.com/r/arcor2/arcor2_upload_kinali/tags?page=1&ordering=last_updated&name=0.11.0), [pypi](https://pypi.org/project/arcor2-kinali/0.11.0/)).
  
### arcor2_kinect_azure

[README](src/python/arcor2_kinect_azure/README.md) | [CHANGELOG](src/python/arcor2_kinect_azure/CHANGELOG.md)

 - 2021-02-08: [0.2.0](https://github.com/robofit/arcor2/releases/tag/arcor2_kinect_azure%2F0.2.0) ([docker](https://hub.docker.com/r/arcor2/arcor2_kinect_azure/tags?page=1&ordering=last_updated&name=0.2.0), [pypi](https://pypi.org/project/arcor2_kinect_azure/0.2.0/)).

 - 2020-12-14: [0.1.0](https://github.com/robofit/arcor2/releases/tag/arcor2_kinect_azure%2F0.1.0) ([docker](https://hub.docker.com/r/arcor2/arcor2_kinect_azure/tags?page=1&ordering=last_updated&name=0.1.0), [pypi](https://pypi.org/project/arcor2_kinect_azure/0.1.0/)).

 ### arcor2_mocks

[README](src/python/arcor2_mocks/README.md) | [CHANGELOG](src/python/arcor2_mocks/CHANGELOG.md)

 - 2020-10-16: [0.12.0](https://github.com/robofit/arcor2/releases/tag/arcor2_mocks%2F0.12.0) ([docker](https://hub.docker.com/r/arcor2/arcor2_mocks/tags?page=1&ordering=last_updated&name=0.12.0), [pypi](https://pypi.org/project/arcor2-mocks/0.12.0/)).

 - 2021-02-08: [0.11.0](https://github.com/robofit/arcor2/releases/tag/arcor2_mocks%2F0.11.0) ([docker](https://hub.docker.com/r/arcor2/arcor2_mocks/tags?page=1&ordering=last_updated&name=0.11.0), [pypi](https://pypi.org/project/arcor2-mocks/0.11.0/)).

 - 2020-10-19: [0.9.1](https://github.com/robofit/arcor2/releases/tag/arcor2_mocks%2F0.9.1) ([docker](https://hub.docker.com/r/arcor2/arcor2_mocks/tags?page=1&ordering=last_updated&name=0.9.1), [pypi](https://pypi.org/project/arcor2-mocks/0.9.1/)).
 
 ### arcor2_dobot

[README](src/python/arcor2_dobot/README.md) | [CHANGELOG](src/python/arcor2_dobot/CHANGELOG.md)

 - 2021-03-03: [0.2.0](https://github.com/robofit/arcor2/releases/tag/arcor2_dobot%2F0.2.0) ([docker](https://hub.docker.com/r/arcor2/arcor2_dobot/tags?page=1&ordering=last_updated&name=0.2.0), [pypi](https://pypi.org/project/arcor2-dobot/0.2.0/)).

 - 2020-10-19: [0.1.0](https://github.com/robofit/arcor2/releases/tag/arcor2_dobot%2F0.1.0) ([docker](https://hub.docker.com/r/arcor2/arcor2_dobot/tags?page=1&ordering=last_updated&name=0.1.0), [pypi](https://pypi.org/project/arcor2-dobot/0.1.0/)).
 
 ## Publications
 
 Comming soon!
