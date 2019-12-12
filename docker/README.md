# Docker environment

This document describes resources needed for building and running docker images with arcor2

## Dockerfiles

 - **Dockerfile-base** - base image for **arserver**, **build** and **execution** services
 - **Dockerfile-arserver** - image with arserver
 - **Dockerfile-build** - image with build service
 - **Dockerfile-execution** - image with execution service

## Docker compose files

 - **docker-compose.yml** 
	 - Basic way to run current stable version of arcor
	 - run with: docker-compose up
 - **docker-compose.devel.yml**
	 - devel version running non-stable version (newest build)
	 - run with: docker-compose -f docker-compose.yml -f docker-compose.devel.yml up

## Building images
With each push to the robofit/arcor2 repository, all images are builded with the latest tag on dockerhub. Building instructions for all images follows. 

 - **Base image** 
	 - DO NOT build manualy, unless you know what are you doing. Use base image from dockerhub (automaticaly builded with each push or release)
	 - docker build . -f docker/Dockerfile-base -t arcor2/arcor2_base:version
 - **Arserver**
	 - docker build . -f docker/Dockerfile-arserver -t arcor2/arcor2_arserver:version
 - **Build**
	 - docker build . -f docker/Dockerfile-build -t arcor2/arcor2_build:version
 - **Execute**
	 - docker build . -f docker/Dockerfile-execute -t arcor2/arcor2_execute:version

## Releasing a new version
To release a new version of ARCOR2, follow this procedure

 1. Update version info
	 1. VERSION file in repository root
	 2. Update base image version (FROM statement) in dockerfiles of all services
	 3. Update images version info in docker-compose.yml
 2. Push all changes to arcor2 repository
 3. Create tag/release with new version
 4. Wait until base image with version tag is build on dockerhub
 5. Build all services using build commands above
 6. Push services to dockerhub
	 7. docker push service_name
