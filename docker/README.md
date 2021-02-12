
# Docker environment

This document describes resources needed for building and running docker images with arcor2.

## Running in docker:

Select one of the docker-compose files in respective folders (currently fit-demo and kinali-demo) and runs following commands in the folder.

### Prerequisites:

- docker
- docker-compose


### Run system 

Compose files always contain the latest released versions of services. If you need some other version, please modify the compose file according to your needs. 

#### Windows

```bash
docker-compose up
```


#### Linux

```bash
sudo -E docker-compose up
```

## Uploading object_types to project service
Use arcor2_upload_kinali or arcor2_upload_fit_demo image to upload all object types in the corresponding demo to project service. For more information see README.md in the demo folder (fit-demo and kinali-demo).


## Dockerfiles

 - **Dockerfile-base** - base image for building process
 - **Dockerfile-dist-base** - base image for all services
 - **Dockerfile-devel** - image with all services installed as python packages (for development only)
 - **Dockerfile-arserver** - image with arserver
 - **Dockerfile-build** - image with build service
 - **Dockerfile-execution** - image with execution service
 - **Dockerfile-execution-proxy** - image with execution service REST proxy
 - **Dockerfile-mocks** - image with scene and project mockups
 - **Dockerfile-upload-kinali** - image for uploading of kinali object types to project service 

## Building images
 - Clone this repo to your computer. First build base image and dist base image, then any other image you want. 
 - Run in /arcor2/ folder
 - **Base image** 
 	 - docker build . -f docker/Dockerfile-base -t arcor2/arcor2_base:VERSION
 - **Dist base image** 
 	 - docker build . -f docker/Dockerfile-dist-base -t arcor2/arcor2_dist_base:VERSION
 - **Arserver**
	 - docker build . -f docker/Dockerfile-arserver -t arcor2/arcor2_arserver :\$(cat ../src/python/arcor2_arserver/VERSION) --build-arg version=VERSION
 - **Build**
	 - docker build . -f docker/Dockerfile-build -t arcor2/arcor2_build:\$(cat ../src/python/arcor2_build/VERSION) --build-arg version=VERSION
 - **Execution**
	 - docker build . -f docker/Dockerfile-execution -t arcor2/arcor2_execution :\$(cat ../src/python/arcor2_execution/VERSION) --build-arg version=VERSION
 - ...and so on. Or run build.sh script

## Releasing a new version

TBA
