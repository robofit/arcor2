#!/bin/bash
VERSION=`python3 ../setup.py --version`
#VERSION='calibration.1'
docker build -f Dockerfile-arserver -t arcor2/arcor2_arserver:$VERSION  ../ --build-arg version=$VERSION
docker build -f Dockerfile-build -t arcor2/arcor2_build:$VERSION --build-arg version=$VERSION ../
docker build -f Dockerfile-execution -t arcor2/arcor2_execution:$VERSION --build-arg version=$VERSION ../
docker build -f Dockerfile-mocks -t arcor2/arcor2_mocks:$VERSION --build-arg version=$VERSION ../
