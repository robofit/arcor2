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

 - 2020-10-30: [0.9.2](https://github.com/robofit/arcor2/releases/tag/arcor2%2F0.9.2) ([pypi](https://pypi.org/project/arcor2/0.9.2/)).
 
 - 2020-10-19: [0.9.1](https://github.com/robofit/arcor2/releases/tag/arcor2%2F0.9.1) ([pypi](https://pypi.org/project/arcor2/0.9.1/)).

 - 2020-10-16: [0.9.0](https://github.com/robofit/arcor2/releases/tag/arcor2%2F0.9.0) ([pypi](https://pypi.org/project/arcor2/0.9.0/)).
 
### arcor2_arserver

[README](src/python/arcor2_arserver/README.md) | [CHANGELOG](src/python/arcor2_arserver/CHANGELOG.md)

 - 2020-10-30: [0.10.1](https://github.com/robofit/arcor2/releases/tag/arcor2_arserver%2F0.10.1) ([docker](https://hub.docker.com/layers/arcor2/arcor2_arserver/0.10.1/images/sha256-4ff3e455dc4aeb7ddb5441c08d5ec9ccb88e7c45a65e38ab31d3b7be4354fee8?context=repo), [pypi](https://pypi.org/project/arcor2-arserver/0.10.1/)).

 - 2020-10-22: [0.10.0](https://github.com/robofit/arcor2/releases/tag/arcor2_arserver%2F0.10.0) ([docker](https://hub.docker.com/layers/arcor2/arcor2_arserver/0.10.0/images/sha256-1b86fc431d1e80eb675f64fb7fa41dc6c3715451594a4b879cd33b32f5444a33?context=repo), [pypi](https://pypi.org/project/arcor2-arserver/0.10.0/)).

 - 2020-10-19: [0.9.1](https://github.com/robofit/arcor2/releases/tag/arcor2_arserver%2F0.9.1) ([docker](https://hub.docker.com/layers/arcor2/arcor2_arserver/0.9.1/images/sha256-50248642745c80a33dfb9eb57734baba5ffbe8226da314a2653f1fb4980d8f0a?context=repo), [pypi](https://pypi.org/project/arcor2-arserver/0.9.1/)).

 
### arcor2_arserver_data

[README](src/python/arcor2_arserver_data/README.md) | [CHANGELOG](src/python/arcor2_arserver_data/CHANGELOG.md)

 - 2020-10-30: [0.9.2](https://github.com/robofit/arcor2/releases/tag/arcor2_arserver_data%2F0.9.2) ([pypi](https://pypi.org/project/arcor2-arserver-data/0.9.2/)).

 - 2020-10-19: [0.9.1](https://github.com/robofit/arcor2/releases/tag/arcor2_arserver_data%2F0.9.1) ([pypi](https://pypi.org/project/arcor2-arserver-data/0.9.1/)).

 - 2020-09-24: [0.8.0](https://github.com/robofit/arcor2/releases/tag/arcor2_arserver_data%2F0.8.0) ([pypi](https://pypi.org/project/arcor2-arserver-data/0.8.0/)).


### arcor2_build

[README](src/python/arcor2_build/README.md) | [CHANGELOG](src/python/arcor2_build/CHANGELOG.md)

- 2020-10-30: [0.9.2](https://github.com/robofit/arcor2/releases/tag/arcor2_build%2F0.9.2) ([docker](https://hub.docker.com/layers/arcor2/arcor2_build/0.9.2/images/sha256-247def7bd8839f001c64870cd236510cb6f3f0052edc7ba08672223cd6bb3738?context=repo), [pypi](https://pypi.org/project/arcor2-build/0.9.2/)).

 - 2020-10-19: [0.9.1](https://github.com/robofit/arcor2/releases/tag/arcor2_build%2F0.9.1) ([docker](https://hub.docker.com/layers/arcor2/arcor2_build/0.9.1/images/sha256-b78e0e61e0c730cc6042a1b63e7af0b9e61616c88ae50269aff7a085d15a8ea9?context=repo), [pypi](https://pypi.org/project/arcor2-build/0.9.1/)).

 - 2020-10-16: [0.9.0](https://github.com/robofit/arcor2/releases/tag/arcor2_build%2F0.9.0) ([docker](https://hub.docker.com/layers/arcor2/arcor2_build/0.9.0/images/sha256-b2e3d3c691c3f9aacb6304b43499574bb21c29848c13ebd06b826674cc345bda?context=repo), [pypi](https://pypi.org/project/arcor2-build/0.9.0/)).

### arcor2_build_data

[README](src/python/arcor2_build_data/README.md) | [CHANGELOG](src/python/arcor2_build_data/CHANGELOG.md)

 - 2020-10-19: [0.8.1](https://github.com/robofit/arcor2/releases/tag/arcor2_build_data%2F0.8.1) ([pypi](https://pypi.org/project/arcor2-build-data/0.8.1/)).

 - 2020-09-24: [0.8.0](https://github.com/robofit/arcor2/releases/tag/arcor2_build_data%2F0.8.0) ([pypi](https://pypi.org/project/arcor2-build-data/0.8.0/)).

### arcor2_calibration

[README](src/python/arcor2_calibration/README.md) | [CHANGELOG](src/python/arcor2_calibration/CHANGELOG.md)

### arcor2_calibration_data

[README](src/python/arcor2_calibration_data/README.md) | [CHANGELOG](src/python/arcor2_calibration_data/CHANGELOG.md)

### arcor2_execution

[README](src/python/arcor2_execution/README.md) | [CHANGELOG](src/python/arcor2_execution/CHANGELOG.md)

 - 2020-10-22: [0.9.0](https://github.com/robofit/arcor2/releases/tag/arcor2_execution%2F0.9.0) ([docker](https://hub.docker.com/layers/arcor2/arcor2_execution/0.9.0/images/sha256-72cbc22076527870d3afc803e26e72a9b2c2b3e595180e1fbe8c99ca1383715e?context=repo), [pypi](https://pypi.org/project/arcor2-execution/0.9.0/)).

 - 2020-10-19: [0.8.1](https://github.com/robofit/arcor2/releases/tag/arcor2_execution%2F0.8.1) ([docker](https://hub.docker.com/layers/arcor2/arcor2_execution/0.8.1/images/sha256-83e0414b7faf77efc2960cc6a8211e344b1fe9c1e689a6f68ddc9da64b86c9f8?context=repo), [pypi](https://pypi.org/project/arcor2-execution/0.8.1/)).

 - 2020-09-24: [0.8.0](https://github.com/robofit/arcor2/releases/tag/arcor2_execution%2F0.8.0) ([docker](https://hub.docker.com/layers/arcor2/arcor2_execution/0.8.0/images/sha256-be37787d97008044f72ac8f1a4ff365da7b0b36069c5b77e5fab2d2c8f2407b3?context=repo), [pypi](https://pypi.org/project/arcor2-execution/0.8.0/)).
 
### arcor2_execution_data

[README](src/python/arcor2_execution_data/README.md) | [CHANGELOG](src/python/arcor2_execution_data/CHANGELOG.md)

 - 2020-10-22: [0.9.0](https://github.com/robofit/arcor2/releases/tag/arcor2_execution_data%2F0.9.0) ([pypi](https://pypi.org/project/arcor2-execution-data/0.9.0/)).

 - 2020-10-19: [0.8.1](https://github.com/robofit/arcor2/releases/tag/arcor2_execution_data%2F0.8.1) ([pypi](https://pypi.org/project/arcor2-execution-data/0.8.1/)).

 - 2020-09-24: [0.8.0](https://github.com/robofit/arcor2/releases/tag/arcor2_execution_data%2F0.8.0) ([pypi](https://pypi.org/project/arcor2-execution-data/0.8.0/)).
 
### arcor2_execution_rest_proxy

[README](src/python/arcor2_execution_rest_proxy/README.md) | [CHANGELOG](src/python/arcor2_execution_rest_proxy/CHANGELOG.md)

 - 2020-10-22: [0.8.2](https://github.com/robofit/arcor2/releases/tag/arcor2_execution_rest_proxy%2F0.8.2) ([docker](https://hub.docker.com/layers/arcor2/arcor2_execution_proxy/0.8.2/images/sha256-008d277073885d1b4f42ac634ba8c96be3ed3456d79427e4de5c769b9320d4fc?context=repo), [pypi](https://pypi.org/project/arcor2-execution-rest-proxy/0.8.2/)).

 - 2020-10-19: [0.8.1](https://github.com/robofit/arcor2/releases/tag/arcor2_execution_rest_proxy%2F0.8.1) ([docker](https://hub.docker.com/layers/arcor2/arcor2_execution_proxy/0.8.1/images/sha256-ae503bc7d78e1dda256efd9d78ce8cbfd41b4628d3ec429028b603272bbcf435?context=repo), [pypi](https://pypi.org/project/arcor2-execution-rest-proxy/0.8.1/)).

 - 2020-09-24: [0.8.0](https://github.com/robofit/arcor2/releases/tag/arcor2_execution_rest_proxy%2F0.8.0) ([docker](https://hub.docker.com/layers/arcor2/arcor2_execution_proxy/0.8.0/images/sha256-e24d1334756d6f3c12fa5686cc055a4acbe5e539eaab44565d2edf8db7db2bc2?context=repo), [pypi](https://pypi.org/project/arcor2-execution-rest-proxy/0.8.0/)).
 
### arcor2_fit_demo

[README](src/python/arcor2_fit_demo/README.md) | [CHANGELOG](src/python/arcor2_fit_demo/CHANGELOG.md)

- 2020-10-19: [0.2.1](https://github.com/robofit/arcor2/releases/tag/arcor2_fit_demo%2F0.2.1) ([docker](https://hub.docker.com/layers/arcor2/arcor2_upload_fit_demo/0.2.1/images/sha256-b3ea0533150814e69d03b7ed6f879d1d05eaf2001b77cab6486db1f3dc7cdffa?context=repo), [pypi](https://pypi.org/project/arcor2-fit-demo/0.2.1/)).

- 2020-09-24: [0.2.0](https://github.com/robofit/arcor2/releases/tag/arcor2_fit_demo%2F0.2.0) ([docker](https://hub.docker.com/layers/arcor2/arcor2_upload_fit_demo/0.2.0/images/sha256-e9d5aa80c3ccd073d4aa438a8c38d3aaaf19df020126264c0b75d0f20fe1ef41?context=repo), [pypi](https://pypi.org/project/arcor2-fit-demo/0.2.0/)).

### arcor2_kinali

[README](src/python/arcor2_kinali/README.md) | [CHANGELOG](src/python/arcor2_kinali/CHANGELOG.md)

- 2020-10-30: [0.9.2](https://github.com/robofit/arcor2/releases/tag/arcor2_kinali%2F0.9.2) ([docker](https://hub.docker.com/layers/arcor2/arcor2_upload_kinali/0.9.2/images/sha256-548d90bd568f60606a3cde61b5dd5c0ed531ca0f0057115432550d88c121b13a?context=repo), [pypi](https://pypi.org/project/arcor2-kinali/0.9.2/)).

 - 2020-10-16: [0.9.1](https://github.com/robofit/arcor2/releases/tag/arcor2_kinali%2F0.9.1) ([docker](https://hub.docker.com/layers/arcor2/arcor2_upload_kinali/0.9.1/images/sha256-5a49845e5c63e74b055aa2b15bbc4c48060837eff9344f6c87d64e5b023e21ae?context=repo), [pypi](https://pypi.org/project/arcor2-kinali/0.9.1/)).

 - 2020-10-16: [0.9.0](https://github.com/robofit/arcor2/releases/tag/arcor2_kinali%2F0.9.0) ([docker](https://hub.docker.com/layers/arcor2/arcor2_upload_kinali/0.9.0/images/sha256-00bbecb82fd7456e3374e4960ce98362cb4d164758dbb4a59a39a05612dc1535?context=repo), [pypi](https://pypi.org/project/arcor2-kinali/0.9.0/)).
  
 ### arcor2_mocks

[README](src/python/arcor2_mocks/README.md) | [CHANGELOG](src/python/arcor2_mocks/CHANGELOG.md)

 - 2020-10-19: [0.9.1](https://github.com/robofit/arcor2/releases/tag/arcor2_mocks%2F0.9.1) ([docker](https://hub.docker.com/layers/arcor2/arcor2_mocks/0.9.1/images/sha256-176c39d079ec975a34ae3c89578fce80b508d377799b8171f2e67085f22f95b2?context=repo), [pypi](https://pypi.org/project/arcor2-mocks/0.9.1/)).

 - 2020-10-16: [0.9.0](https://github.com/robofit/arcor2/releases/tag/arcor2_mocks%2F0.9.0) ([docker](https://hub.docker.com/layers/arcor2/arcor2_mocks/0.9.0/images/sha256-17583926c76b23c4201555b6cdcf603d65c9c961bfd014710574cdddb2bb474c?context=repo), [pypi](https://pypi.org/project/arcor2-mocks/0.9.0/)).

 - 2020-09-23: [0.8.0](https://github.com/robofit/arcor2/releases/tag/arcor2_mocks%2F0.8.0) ([docker](https://hub.docker.com/layers/arcor2/arcor2_mocks/0.8.0/images/sha256-d5d233d35059e3125b9080f073e42cf541a5a9137b777e281c94c2f31da8ea51?context=repo), [pypi](https://pypi.org/project/arcor2-mocks/0.8.0/)).
 
 ## Publications
 
 Comming soon!
