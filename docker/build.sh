#!/bin/bash
#VERSION=`python3 ../setup.py --version`
VERSION='pants'
docker build -f Dockerfile-dist-base -t arcor2/arcor2_dist_base:$VERSION  ../ --build-arg version=$VERSION
docker build -f Dockerfile-arserver -t arcor2/arcor2_arserver:$VERSION  ../ --build-arg version=$VERSION
docker build -f Dockerfile-build -t arcor2/arcor2_build:$VERSION --build-arg version=$VERSION ../
docker build -f Dockerfile-execution -t arcor2/arcor2_execution:$VERSION --build-arg version=$VERSION ../
docker build -f Dockerfile-execution-proxy -t arcor2/arcor2_execution_proxy:$VERSION --build-arg version=$VERSION ../
docker build -f Dockerfile-mocks -t arcor2/arcor2_mocks:$VERSION --build-arg version=$VERSION ../
docker build -f Dockerfile-upload-fit-demo -t arcor2/arcor2_upload_fit_demo:$VERSION --build-arg version=$VERSION ../
#docker build -f Dockerfile-mocks -t arcor2/arcor2_mocks:$VERSION --build-arg version=$VERSION ../
