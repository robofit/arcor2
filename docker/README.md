
# Docker environment

This document describes resources needed for building and running docker images with arcor2

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

## Docker compose files

 - **docker-compose.yml** 
	 - Basic way to run any version of arcor2
	 - Desired version is set using the ARCOR2_VERSION environment variable
		 - *export ARCOR2_VERSION=\$(cat arcor2/VERSION)* for latest available stable version
		 - *export ARCOR2_VERSION=latest* for latest available build
		 - *export ARCOR2_VERSION=0.1.2* for specific version
	 - run with:  *sudo -E docker-compose up*
		 - the -E parameter is needed for passing environment variables to the docker-compose context

## Building images
 - clone this repo to your computer
 - run in /arcor2/ folder
 - **Base image** 
 	 - *docker build . -f docker/Dockerfile-base -t arcor2/arcor2_base:\$(cat arcor2/VERSION)*
 - **Arserver**
	 - *docker build . -f docker/Dockerfile-arserver -t arcor2/arcor2_arserver :\$(cat arcor2/VERSION) --build-arg version=\$(cat arcor2/VERSION)*
 - **Build**
	 - *docker build . -f docker/Dockerfile-build -t arcor2/arcor2_build:\$(cat arcor2/VERSION) --build-arg version=$(cat arcor2/VERSION)*
 - **Execution**
	 - *docker build . -f docker/Dockerfile-execution -t arcor2/arcor2_execution :\$(cat arcor2/VERSION) --build-arg version=\$(cat arcor2/VERSION)*
 - ... and so on. Or run build.sh script

## Releasing a new version

TBA
