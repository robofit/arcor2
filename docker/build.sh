#!/bin/bash
VERSION="0.8.0rc5"
docker build -f Dockerfile-dist-base -t arcor2/arcor2_dist_base:`cat ../src/python/arcor2/VERSION`  ../ --build-arg version=$VERSION
docker build -f Dockerfile-arserver -t arcor2/arcor2_arserver:`cat ../src/python/arcor2_arserver/VERSION`  ../ --build-arg version=$VERSION
docker build -f Dockerfile-build -t arcor2/arcor2_build:`cat ../src/python/arcor2_build/VERSION` --build-arg version=$VERSION ../
docker build -f Dockerfile-execution -t arcor2/arcor2_execution:`cat ../src/python/arcor2_execution/VERSION` --build-arg version=$VERSION ../
docker build -f Dockerfile-execution-proxy -t arcor2/arcor2_execution_proxy:`cat ../src/python/arcor2_execution_rest_proxy/VERSION` --build-arg version=$VERSION ../
docker build -f Dockerfile-mocks -t arcor2/arcor2_mocks:$VERSION --build-arg version=`cat ../src/python/arcor2_mocks/VERSION` ../
docker build -f Dockerfile-devel -t arcor2/arcor2_devel:$VERSION --build-arg version=$VERSION ../
docker build -f Dockerfile-upload-fit-demo -t arcor2/arcor2_upload_fit_demo:`cat ../src/python/arcor2_fit_demo/VERSION` --build-arg version=$VERSION ../
docker build -f Dockerfile-upload-kinali -t arcor2/arcor2_upload_kinali:`cat ../src/python/arcor2_kinali/VERSION` --build-arg version=$VERSION ../
#docker build -f Dockerfile-mocks -t arcor2/arcor2_mocks:$VERSION --build-arg version=$VERSION ../
