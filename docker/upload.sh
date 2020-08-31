#!/bin/bash 
VERSION=`python3 ../setup.py --version`
#VERSION='0.8.0.b2'
docker image push arcor2/arcor2_base:$VERSION
docker image push arcor2/arcor2_arserver:$VERSION
docker image push arcor2/arcor2_execution:$VERSION
docker image push arcor2/arcor2_build:$VERSION
docker image push arcor2/arcor2_mocks:$VERSION
