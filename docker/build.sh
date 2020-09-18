#!/bin/bash
#VERSION=`python3 ../setup.py --version`
VERSION='0.8.0rc3'
docker build -f Dockerfile-dist-base -t arcor2/arcor2_dist_base:$VERSION  ../ --build-arg version=$VERSION
docker build -f Dockerfile-arserver -t arcor2/arcor2_arserver:`cat ../src/python/arcor2_arserver/VERSION`  ../ --build-arg version=$VERSION
docker build -f Dockerfile-build -t arcor2/arcor2_build:`cat ../src/python/arcor2_arserver/VERSION` --build-arg version=$VERSION ../
docker build -f Dockerfile-execution -t arcor2/arcor2_execution:`cat ../src/python/arcor2_arserver/VERSION` --build-arg version=$VERSION ../
docker build -f Dockerfile-execution-proxy -t arcor2/arcor2_execution_proxy:`cat ../src/python/arcor2_arserver/VERSION` --build-arg version=$VERSION ../
docker build -f Dockerfile-mocks -t arcor2/arcor2_mocks:$VERSION --build-arg version=`cat ../src/python/arcor2_arserver/VERSION` ../
docker build -f Dockerfile-upload-fit-demo -t arcor2/arcor2_upload_fit_demo:`cat ../src/python/arcor2_arserver/VERSION` --build-arg version=`cat ../src/python/arcor2_arserver/VERSION` ../
#docker build -f Dockerfile-mocks -t arcor2/arcor2_mocks:$VERSION --build-arg version=$VERSION ../
