
# Docker environment

This document describes resources needed for building and running docker images with arcor2

## Dockerfiles

 - **Dockerfile-base** - base image for **arserver**, **build** and **execution** services
 - **Dockerfile-arserver** - image with arserver
 - **Dockerfile-build** - image with build service
 - **Dockerfile-execution** - image with execution service

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
With each push to the robofit/arcor2 repository, all images are builded with the latest tag on dockerhub. Specific releases needs to be build manualy (except for base image). Building instructions for all images follows. 

 - **Base image** 
	 - DO NOT build manualy, unless you know what are you doing. Use base image from dockerhub (automaticaly builded with each push or release)
	 - *docker build . -f docker/Dockerfile-base -t arcor2/arcor2_base:\$(cat arcor2/VERSION)*
 - **Arserver**
	 - *docker build . -f docker/Dockerfile-arserver -t arcor2/arcor2_arserver :\$(cat arcor2/VERSION) --build-arg version=\$(cat arcor2/VERSION)*
 - **Build**
	 - *docker build . -f docker/Dockerfile-build -t arcor2/arcor2_build:\$(cat arcor2/VERSION) --build-arg version=$(cat arcor2/VERSION)*
 - **Execute**
	 - *docker build . -f docker/Dockerfile-execution -t arcor2/arcor2_execution :\$(cat arcor2/VERSION) --build-arg version=\$(cat arcor2/VERSION)*

## Releasing a new version
To release a new version of ARCOR2, follow this procedure

 1. Update version info
	 1. VERSION file in arcor2 package
 2. Push all changes to arcor2 repository
 3. Create tag/release with new version
 4. Wait until base image with version tag is build on dockerhub
 5. Build all services using build commands above
 6. Push services to dockerhub
	 7. docker push service_name
